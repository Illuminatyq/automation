<?php

namespace App\Legacy;

use App\Constants\Enum\DF;
use App\Constants\Enum\Events;
use App\Constants\Enum\TZ;
use App\Constants\Enum\HTTPMethod;
use App\Constants\RabbitQueue;
use App\Constants\SipEndpointParams;
use App\Constants\SocketEventRegistry;
use App\Constants\StorageScope;
use App\Constants\Time;
use App\Constants\Vat\VatLeg;
use App\Constants\Vat\VatProvider;
use App\Core\Cache;
use App\Core\DB;
use App\Core\File;
use App\Core\IO;
use App\Core\Locale;
use App\Core\Moment;
use App\Core\Plan;
use App\Events\EventManager;
use App\Exceptions\System\Provider\SocketException;
use App\Helpers\FunctionsHelper;
use App\Helpers\InstanceHelper;
use App\Liner;
use App\Objects\SipEndpoint;
use App\Providers\RabbitProvider;
use App\Providers\SocketProvider;
use App\Providers\UisApiProvider;
use App\Providers\VoxProvider;
use App\Repositories\SipEndpointRepository;
use App\Services\BlockListService;
use App\Services\DiBotService;
use App\Services\SipEndpointService;
use App\Services\SocketService;
use App\Services\LogService;
use DateTime;
use Exception;

/**
 * Class Vats
 * Предназначен для работы с провайдерами Vox и Uis
 * @deprecated Legacy classes shouldn't be used.
 */
final class Vats extends Controller
{
    public int $predictiveRelativeFlowMaxCount = 100;

    public static function getHangupStatus($leadId, $userId, $sessionId) : bool
    {
        $string = false;

        try {
            $params = [
                'order'  => [],
                'limit'  => 1,
                'filter' => [
                    'UF_LEAD_ID'         => (int) $leadId,
                    'UF_OPERATOR_ID'     => (int) $userId,
                    'UF_CALL_SESSION_ID' => (int) $sessionId,
                ],
                'select' => [
                    'ID',
                    'UF_HANGUP',
                ],
            ];

            $res = DB::getList(Callresults::DB_TABLE_NAME_HANGUPS, $params)->fetch();

            if (!empty($res)) {
                $string = $res['UF_HANGUP'];
            }
        } catch (Exception $e) {
            # TODO: add real handler
        }

        return $string;
    }

    /**
     * Получаем коды целевых звонков
     *
     * @return array
     * */
    public function getSuccessStatusesMap() : array
    {
        $arrResult = [];

        $statusesMap = $this->getStatusesMap();

        foreach ($statusesMap as $statusCode => $statusType) {
            if (in_array($statusType, ['dark', 'already-success']) && !in_array($statusCode, $arrResult)) {
                $arrResult[] = $statusCode;
            }
        }

        return $arrResult;
    }

    /**
     * @todo удалить после заливки таски в прод https://tracker.yandex.ru/LINER-495
     * @deprecated
     */
    public function getStatusesMapOld() : array
    {
        $statusesMap = [
            '50000063669' => 'dark', // Переведен в КЦ -> В работе
            '50000064100' => 'already-success', // ОП перезвонил

            '22222222222' => 'primary', // Не дождался перевода в ОП -> Новый
            '77777777777' => 'primary', // Упущен телефонией -> Новый
            '11111111111' => 'primary', // Исчерпан лимит дозвонов -> Новый
            '88888888888' => 'primary', // Не принят оператором -> Новый
            '55555555555' => 'primary', // Дозвон прекращен -> Новый
            '50000063670' => 'primary', // Не ответил -> Новый
            '50000063673' => 'primary', // Бросил трубку -> Новый
            '50000063674' => 'primary', // Проблемы со связью -> Новый
            '50000063675' => 'primary', // Не дождался перевода на КЦ -> Новый
            '33333333333' => 'primary', // Автоответчик -> Новый
            '50000063681' => 'primary', // Просьба перезвонить -> Новый (просьба перезвонить)
            '50000063682' => 'primary', // Не дозвонились до КЦ застройщика -> Новый (просьба перезвонить)

            '50000063700' => 'primary', //Неудобно -> Новый

            '50000160000' => 'fail-straight', // Не заинтересован, иная потребность -> Не целевой, подбор

            '50000063676' => 'danger', // Отказ от консультации -> Брак
            '50000063677' => 'danger', // Отказ от перевода на КЦ -> Брак
            '50000063678' => 'danger', // КЦ отказался от Лида -> Брак
            '50000063679' => 'danger', // Клиент не заинтересован -> Брак
            '50000063680' => 'danger', // Нечего предложить -> Брак
            '40000154334' => 'danger', //  Не зарегистрирован в сети -> Брак
            '40000154335' => 'danger', // Номер не принадлежит клиенту -> Брак
            '50000063683' => 'danger', // Иное -> Брак
        ];

        EventManager::dispatch(Events::VATS_AFTER_STATUSES_MAP, $statusesMap);

        return $statusesMap;
    }

    /**
     * @return array
     */
    protected function getStatusesMap() : array
    {
        $cacheHit = md5('vatsStatusesMap');

        if ($cacheResult = Cache::get($cacheHit)) {

            if(!empty($cacheResult) && is_array($cacheResult)) {
                return $cacheResult;
            }
        }

        $result = [];

        $callStatusData = (new Callstatuseslist())->getCallStatusList([], null, 'UF_SORT ASC');

        foreach ($callStatusData as $item) {
            $result[$item['UF_STATUS_CODE']] = $item['actionCode'];
        }

        Cache::set($cacheHit, $result, 5);

        return $result;
    }

    /**
     * Возращаем контроллер Hooks
     *
     * @return Hooks
     */
    public function getHookController()
    {
        return new Hooks();
    }

    public function getConfUisDataApiUrl() : string
    {
        return IO::readEnv('CONF_UIS_DATA_API_URL');
    }

    public function getConfUisPhoneNumber() : string
    {
        return IO::readEnv('CONF_UIS_DEFAULT_PHONE_NUMBER');
    }

    /**
     * Curl запрос
     *
     * @param $url
     * @param $method
     * @param $id
     * @param $params
     *
     * @return mixed
     */
    public function sendRequest($url, $method, $id, $params = [])
    {
        $payload = json_encode(
            [
                'jsonrpc' => '2.0',
                'id'      => $id,
                'method'  => $method,
                'params'  => array_merge(['access_token' => $this->getConfUisAccessToken()], $params),
            ]
        );

        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type:application/json']);
        curl_setopt($ch, CURLOPT_POST, 1);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $payload);

        $res = curl_exec($ch);
        curl_close($ch);

        $result = json_decode($res, 1);

        if (!empty($result['result']['metadata'])) {
            $this->checkApiLimits($result['result']['metadata']);
        }

        if (!empty($result['result'])) {
            return $result['result'];
        }

        return false;
    }

    public function getConfUisAccessToken() : string
    {
        return IO::readEnv('CONF_UIS_ACCESS_TOKEN');
    }

    /**
     * Проверка на лимиты в uis
     * Проверяем дневной лимит если 90 % и выше шлем уведомление в Slack
     * Проверяем лимит в минуту если 90 % и выше шлем уведомление в Slack
     *
     * @param $metaData
     *
     * @return bool
     */
    private function checkApiLimits($metaData)
    {
        /*
         * Desc: https://comagic.github.io/call-api/
         *
         * day_limit - Текущие лимит баллов в день
         * day_remaining - Какое количество баллов осталось до достижения дневного лимита
         * day_reset - Время в секундах через которое дневной лимит будет сброшен
         * minute_limit - Текущие лимит баллов за минуту
         * minute_remaining - Какое количество баллов осталось до достижения минутного лимита
         * minute_reset - Время в секундах через которое минутный лимит будет сброшен
         * current_version_depricated - Признак, говорящий, что в ближайшие пару месяцев старая версия может стать недоступной.
         * current_version - Вызванная версия
         * latest_version - Последняя доступная версия
         */

        if (!empty($metaData['limits'])) {
            // Проверяем дневной лимит
            $dayUsed = $metaData['limits']['day_limit'] - $metaData['limits']['day_remaining'];
            $dayUsedPercentage = ($metaData['limits']['day_remaining'] <= 0) ? 100 : round(
                $dayUsed / $metaData['limits']['day_limit'] * 100
            );
            if ($dayUsedPercentage >= 90) {
                $msgText = ":bangbang: *'" . Liner::t('Attention') . "'!*\n'" . Liner::t(
                        'Spent'
                    ) . "'*" . $dayUsedPercentage . "*% '" . Liner::t(
                        'daily API request resource'
                    ) . "'.\n'" . Liner::t(
                        'remaining requests'
                    ) . "': *" . $metaData['limits']['day_remaining'] . " '" . Liner::t(
                        'from'
                    ) . "' " . $metaData['limits']['day_limit'] . "*.";
                    LogService::info(msgData: compact('metaData', 'dayUsedPercentage'), commentNotification: $msgText);

                return false;
            }

            // Проверяем лимит в минуту
            $minuteUsed = $metaData['limits']['minute_limit'] - $metaData['limits']['minute_remaining'];
            $minuteRemainingPercentage = ($metaData['limits']['minute_remaining'] <= 0) ? 100 : round(
                $minuteUsed / $metaData['limits']['minute_limit'] * 100
            );
            if ($minuteRemainingPercentage >= 90) {
                $msgText = ":bangbang: *'" . Liner::t('Attention') . "'!*\n'" . Liner::t(
                        'Spent'
                    ) . "' *" . $minuteRemainingPercentage . "*% '" . Liner::t(
                        'minute API requests resource'
                    ) . "'.\n '" . Liner::t(
                        'remaining requests'
                    ) . "': *" . $metaData['limits']['minute_remaining'] . " '" . Liner::t(
                        'from'
                    ) . "' " . $metaData['limits']['minute_limit'] . "*.";
                    LogService::info(msgData: compact('metaData', 'minuteRemainingPercentage'), commentNotification: $msgText);

                return false;
            }
        }

        return true;
    }

    //
    // Core methods and functions

    /**
     * Список операторов
     *
     * @return array
     */
    public function getEmployeeStatusList()
    {
        $params = [
            'order'  => ['UF_SORT' => 'ASC'],
            'select' => ['*'],
        ];

        $callCenterStatusesRes = DB::getList(Callcenterstatushistory::DB_TABLE_NAME_STATUSES_LIST, $params);

        $resStatuses = [];
        while ($callCenterStatusItem = $callCenterStatusesRes->fetch()) {
            $resStatuses[] = $callCenterStatusItem;
        }

        return $resStatuses;
    }

    /**
     * Возращаем операторов на статусе перерыв
     *
     * @return array
     */
    public function getBreakCallStatus()
    {
        return $this->getCallCenterStatusByFilter(['UF_IS_NOT_AT_WORK' => 1]);
    }

    //
    // Uis modified methods

    /**
     * Возращаем статусы операторов по фильтру
     *
     * @param array $filter
     *
     * @return array
     */
    protected function getCallCenterStatusByFilter($filter)
    {
        $cacheHit = md5('getCallCenterStatusByFilter_' . json_encode($filter));

        if ($cacheResult = Cache::get($cacheHit)) {
            $result = $cacheResult['result'];
        } else {
            $params = [
                'order'  => ['UF_SORT' => 'ASC'],
                'select' => ['*'],
                'limit'  => 1,
                'filter' => $filter,
            ];

            $callCenterStatusItem = DB::getList(Callcenterstatushistory::DB_TABLE_NAME_STATUSES_LIST, $params)->fetch();

            $result = (!empty($callCenterStatusItem)) ? $callCenterStatusItem : [];

            if (!empty($result)) {
                Cache::set($cacheHit, ['result' => $result], 300);
            }
        }

        return $result;
    }

    /**
     * Вывод текущей ситуации по предиктиву
     */
    public function calcPredictiveFlow()
    {
        $callResults = new Callresults();

        $onlinePredictiveEmployees = $this->getOnlinePredictiveEmployees();

        echo '<pre>';
        print_r('Predictive operators: ' . count($onlinePredictiveEmployees));
        echo '</pre>';

        // Получаем текущие вызовы в системе
        $activePredictiveCallsCount = $this->getActivePredictiveCallsCount();

        echo '<pre>';
        print_r('Active predictive calls count: ' . $activePredictiveCallsCount);
        echo '</pre>';

        // Определяем в каких состояниях у нас сейчас сотрудники
        $availableCount = $activeCallCount = $postCallCount = $isAvailableForDialCount = 0;
        foreach ($onlinePredictiveEmployees as $employeeData) {
            if ($employeeData['IS_AVAILABLE']) {
                $availableCount++;
            }

            if ($employeeData['IS_AVAILABLE'] && !$employeeData['IS_ACTIVE_CALL']) {
                $isAvailableForDialCount++;
            }

            if ($employeeData['IS_ACTIVE_CALL']) {
                $activeCallCount++;
            }

            if ($employeeData['IS_POST_CALL']) {
                $postCallCount++;
            }
        }

        echo '<pre>';
        print_r('Available operators count:' . $isAvailableForDialCount);
        echo '</pre>';

        // Поднимаем историю предиктивных вызовов за последние 10 минут
        $timeOffsetMinutes = 10;

        $finishDateObj = new DateTime();
        $startDateObj = clone $finishDateObj;
        $startDateObj->modify('- ' . $timeOffsetMinutes . ' minutes');

        $limit = count($onlinePredictiveEmployees) * 10 * 1.5;
        // Refactored
        $callsRes = $callResults->getCallResultsList(
            [
                'ID',
                'UF_IS_PREDICTIVE',
                'UF_STATUS_CODE',
                'UF_TOTAL_TIME_DURATION',
                'UF_WAIT_TIME_DURATION',
                'UF_TALK_TIME_DURATION',
                'UF_DATE',
                'UF_PREDICTIVE_FLOW_NUMBER',
            ],
            [
                'UF_IS_PREDICTIVE' => 1,
            ],
            $limit
        );

        $totalCallsCount = $successCallsCount = $totalCanceledCallsCount = $totalNotAnsweredCallsCount = $avgPreviousFlowSum = 0;

        // Агрегируем информацию
        //while($callItem = $callsRes->fetch())
        foreach ($callsRes as $callItem) {
            switch ($callItem['UF_STATUS_CODE']) {
                case '55555555555':
                case '88888888888':
                    if ($callItem['UF_STATUS_CODE'] == '55555555555') {
                        $totalCanceledCallsCount++;
                    }
                    if ($callItem['UF_STATUS_CODE'] == '88888888888') {
                        $totalNotAnsweredCallsCount++;
                    }
                break;
                default:
                    $successCallsCount++;
            }

            $avgPreviousFlowSum += $callItem['UF_PREDICTIVE_FLOW_NUMBER'];
            $totalCallsCount++;
        }

        $actualFlowSuccessPercent = (100 / $totalCallsCount) * $successCallsCount;

        echo '<pre>';
        print_r('$actualFlowSuccessPercent : ' . $actualFlowSuccessPercent);
        echo '</pre>';

        $actualFlowCount = (!empty($avgPreviousFlowSum)) ? round($avgPreviousFlowSum / $totalCallsCount) : 1;
        $actualFlowCount = (empty($actualFlowCount)) ? 1 : $actualFlowCount;

        $absolutelyFlowMaximum = $isAvailableForDialCount * 4;

        $newFlowCount = $actualFlowCount + 3;
        $newFlowCount = ($newFlowCount > $absolutelyFlowMaximum) ? $absolutelyFlowMaximum : $newFlowCount;

        echo '<pre>';
        print_r('$actualFlowCount : ' . $actualFlowCount);
        echo '</pre>';

        echo '<pre>';
        print_r('$absolutelyFlowMaximum : ' . $absolutelyFlowMaximum);
        echo '</pre>';

        echo '<pre>';
        print_r('$newFlowCount : ' . $newFlowCount);
        echo '</pre>';

        if ($newFlowCount > $activePredictiveCallsCount) {
            echo '<br>READY FOR INIT';
        }

        exit('--dubug finished');
    }

    /**
     * Онлайн операторы предиктива
     *
     * @return array
     */
    public function getOnlinePredictiveEmployees()
    {
        $voxProvider = new VoxProvider();

        $user = new User();

        $rsUsers = $user->getActiveCallCenterUsersMap();

        $callCenterEmployeesArr = $onlineEmployeesArr = [];

        $employeeStatusMap = $this->getEmployeeStatusesMap(true);

        $phoneFieldCode = match (InstanceHelper::getVatsProviderCode()) {
            VatProvider::VOX => 'UF_VOX_USER_NAME',
            default => 'UF_UIS_ID',
        };

        foreach ($rsUsers as $userData) {
            if (empty($userData[$phoneFieldCode]) || !empty($userData['UF_TRAINING_IS_ENABLED']) || (!empty($employeeStatusMap[$userData['UF_UIS_STATUS']]) && in_array(
                        $employeeStatusMap[$userData['UF_UIS_STATUS']],
                        ['break', 'tech_break', 'not_at_work']
                    ))) {
                continue;
            }

            if ($this->isAllowedByUserPhoneMode('predictive', $userData['UF_PHONE_MODE'])) {
                $callCenterEmployeesArr[] = [
                    'ID'                  => $userData['ID'],
                    'UF_UIS_CALL_SESSION' => $userData['UF_UIS_CALL_SESSION'],
                    'UF_UIS_ID'           => $userData['UF_UIS_ID'],
                    'UF_VOX_USER_NAME'    => $userData['UF_VOX_USER_NAME'],
                    'UF_UIS_STATUS'       => $userData['UF_UIS_STATUS'],
                    'IS_AVAILABLE'        => (!empty($employeeStatusMap[$userData['UF_UIS_STATUS']]) && $employeeStatusMap[$userData['UF_UIS_STATUS']] == 'available'),
                    'IS_ACTIVE_CALL'      => (!empty($userData['UF_UIS_CALL_SESSION'])),
                    'IS_POST_CALL'        => (!empty($userData['UF_IS_POSTCALL'])),
                ];
            }
        }

        if (!empty($callCenterEmployeesArr)) {
            // Проверяем всех сотрудников КЦ на онлайн
            foreach ($callCenterEmployeesArr as $employeeItem) {

                if(!SocketService::checkUserOnline(intval($employeeItem['ID']))) {
                    continue;
                }

                $isReadyForCall = match (InstanceHelper::getVatsProviderCode()) {
                    VatProvider::VOX => (!empty($employeeItem['UF_VOX_USER_NAME']) && $voxProvider->userIsReadyForCall(
                            $employeeItem['UF_VOX_USER_NAME']
                        )),
                    default => (!empty($employeeItem['UF_UIS_ID']) && UisApiProvider::connected(
                            $employeeItem['UF_UIS_ID']
                        )),
                };

                if ($isReadyForCall) {
                    $onlineEmployeesArr[] = $employeeItem;
                }
            }
        }

        return $onlineEmployeesArr;
    }

    /**
     * Возращаем доступные статусы оператора
     *
     * @param bool $flip
     *
     * @return array
     */
    public function getEmployeeStatusesMap($flip = false)
    {
        $cacheHit = md5('getEmployeeStatusesMap_' . $flip);

        if ($cacheResult = Cache::get($cacheHit)) {
            $result = $cacheResult['result'];
        } else {
            $params = [
                'order'  => ['UF_SORT' => 'ASC'],
                'select' => ['*'],
            ];

            $callCenterStatusesRes = DB::getList(Callcenterstatushistory::DB_TABLE_NAME_STATUSES_LIST, $params);

            $result = [];
            while ($callCenterStatusItem = $callCenterStatusesRes->fetch()) {
                if ($callCenterStatusItem['UF_IS_AVAILABLE']) {
                    $result['available'] = intval($callCenterStatusItem['UF_UIS_ID']);
                }
                if ($callCenterStatusItem['UF_IS_ACTIVE_CALL']) {
                    $result['active_call'] = intval($callCenterStatusItem['UF_UIS_ID']);
                }
                if ($callCenterStatusItem['UF_IS_POST_CALL']) {
                    $result['post_call'] = intval($callCenterStatusItem['UF_UIS_ID']);
                }
                if ($callCenterStatusItem['UF_IS_BREAK']) {
                    $result['break'] = intval($callCenterStatusItem['UF_UIS_ID']);
                }
                if ($callCenterStatusItem['UF_IS_TECH_BREAK']) {
                    $result['tech_break'] = intval($callCenterStatusItem['UF_UIS_ID']);
                }
                if ($callCenterStatusItem['UF_IS_NOT_AT_WORK']) {
                    $result['not_at_work'] = intval($callCenterStatusItem['UF_UIS_ID']);
                }
            }

            if (!empty($result) && $flip) {
                $result = array_flip($result);
            }

            if ($result) {
                Cache::set($cacheHit, ['result' => $result], 300);
            }
        }

        return $result;
    }

    public function getActivePredictiveCallsCount()
    {
        $leadsSql = "
            SELECT COUNT(*) as activePredictiveCallsCount
            FROM " . Leads::DB_TABLE_NAME . "
            LEFT JOIN " . Callresults::DB_TABLE_NAME . " 
                on " . Callresults::DB_TABLE_NAME . ".UF_CALL_SESSION_ID = " . Leads::DB_TABLE_NAME . ".UF_UIS_CALL_ID
            WHERE " . Leads::DB_TABLE_NAME . ".UF_STATUS = 'primary' 
                AND " . Leads::DB_TABLE_NAME . ".UF_UIS_CALL_ID > 0 
                AND " . Callresults::DB_TABLE_NAME . ".UF_IS_PREDICTIVE = 1;
        ";

        $leadsRes = DB::query($leadsSql)->fetch();

        return $leadsRes['activePredictiveCallsCount'];
    }

    /**
     * Отправка лидов на дозвон
     * Убедимся, что в массиве есть лиды
     * Убедимся, что есть операторы в предиктивном режиме
     * Ищем подходящий лид для звонка
     * Убедимся, актуально ли данное задание
     * Продолжаем, если позволяет расписание
     * Убедимся, что есть операторы в предиктивном режиме
     * Убедимся, есть ли у нас операторы, способные обработать данный лид
     * Получаем текущие вызовы в системе
     * Если количество активных вызовов меньше полностью доступных сотрудников, то стартуем
     * Cчитатаем максимально возможное количество потоков и если они больше текущих и если процент выше 70 по удачных
     * дозвонам , то стартуем Все проверки пройдены, отправляем лид на дозвон
     *
     * @return true
     */
    public function dialerPredictiveManager($leadsArr)
    {
        // Убедимся, что в массиве есть лиды
        if (empty($leadsArr)) {
            return true;
        }

        // Убедимся, что есть операторы в предиктивном режиме
        $onlinePredictiveEmployees = $this->getOnlinePredictiveEmployees();
        if (empty($onlinePredictiveEmployees)) {
            return true;
        }

        $callResults = new Callresults();

        $leads = new Leads();
        $orders = new Orders();

        $predictiveSuccessPercent = $this->getPredictiveSuccessPercent();

        // Ищем подходящий лид для звонка
        foreach ($leadsArr as $leadItem) {
            // Убедимся, актуально ли данное задание
            // Refactored
            $leadData = $leads->getLeadList(
                [
                    'ID',
                    'UF_STATUS',
                    'UF_UIS_CALL_ID',
                    'UF_CALL_DATE_TIME',
                    'UF_ORDER',
                ],
                [
                    'ID'                => $leadItem['Leads_ID'],
                    'UF_STATUS'         => 'primary',
                    'UF_CALL_DATE_TIME' => $leadItem['Leads_UF_CALL_DATE_TIME'],
                ],
                1
            );

            if (empty($leadData['ID']) || !empty($leadData['UF_UIS_CALL_ID'])) {
                return true;
            }

            // Проверим, все ли ок с заказом
            if (!$orders->callIsAllowed($leadData['UF_ORDER'], 'predictive')) {
                return true;
            }

            // Убедимся, что есть операторы в предиктивном режиме
            $onlinePredictiveEmployees = $this->getOnlinePredictiveEmployees();
            if (empty($onlinePredictiveEmployees)) {
                return true;
            }

            // Убедимся, есть ли у нас операторы, способные обработать данный лид
            $goodEmployees = $this->filterByOrderEmployees($onlinePredictiveEmployees, $leadItem['Leads_UF_ORDER']);
            if (empty($goodEmployees)) {
                continue;
            }

            // Теперь нужно разобраться, стоит ли отправлять лид на дозвон
            $newPredictiveFlowIsAllowed = false;

            // Получаем текущие вызовы в системе
            $activePredictiveCallsCount = $this->getActivePredictiveCallsCount();

            if (empty($activePredictiveCallsCount)) {
                $newPredictiveFlowIsAllowed = true;
            } else {
                // Определяем в каких состояниях у нас сейчас сотрудники
                $availableCount = $activeCallCount = $postCallCount = $isAvailableForDialCount = 0;
                foreach ($onlinePredictiveEmployees as $employeeData) {
                    if ($employeeData['IS_AVAILABLE'] && !$employeeData['IS_ACTIVE_CALL']) {
                        $isAvailableForDialCount++;
                    }
                }

                // Если количество активных вызовов меньше полностью доступных сотрудников, то стартуем
                if ($activePredictiveCallsCount < $isAvailableForDialCount) {
                    $newPredictiveFlowIsAllowed = true;
                } else {
                    $timeOffsetMinutes = 5;

                    $finishDateObj = new DateTime();
                    $startDateObj = clone $finishDateObj;
                    $startDateObj->modify('- ' . $timeOffsetMinutes . ' minutes');

                    $limit = count($onlinePredictiveEmployees) * 10 * 1.5;
                    // Поднимаем историю предиктивных вызовов за последнее время
                    // Refactored
                    $callsRes = $callResults->getCallResultsList(
                        [
                            'ID',
                            'UF_IS_PREDICTIVE',
                            'UF_STATUS_CODE',
                            'UF_TOTAL_TIME_DURATION',
                            'UF_WAIT_TIME_DURATION',
                            'UF_TALK_TIME_DURATION',
                            'UF_DATE',
                            'UF_PREDICTIVE_FLOW_NUMBER',
                        ],
                        [
                            'UF_IS_PREDICTIVE' => 1,
                        ],
                        $limit
                    );

                    $totalCallsCount = $successCallsCount = $avgPreviousFlowSum = 0;

                    // Агрегируем информацию
                    //while($callItem = $callsRes->fetch())
                    foreach ($callsRes as $callItem) {
                        if (!in_array($callItem['UF_STATUS_CODE'], [
                            '55555555555',
                            '88888888888'
                        ])) {
                            $successCallsCount++;
                        }

                        $avgPreviousFlowSum += $callItem['UF_PREDICTIVE_FLOW_NUMBER'];
                        $totalCallsCount++;
                    }

                    // Если информации для анализа недостаточно, то нужно стартовать вызов
                    if (empty($totalCallsCount)) {
                        $newPredictiveFlowIsAllowed = true;
                    } else {
                        if (empty($successCallsCount)) {
                            continue;
                        }

                        $actualFlowSuccessPercent = (100 / $totalCallsCount) * $successCallsCount;

                        if ($actualFlowSuccessPercent < $predictiveSuccessPercent) {
                            continue;
                        }

                        // Теперь нужно посчитать максимально возможное количество потоков
                        // На основе информации о вызовах за последнее время

                        $actualFlowCount = (!empty($avgPreviousFlowSum)) ? round(
                            $avgPreviousFlowSum / $totalCallsCount
                        ) : 1;
                        $actualFlowCount = (empty($actualFlowCount)) ? 1 : $actualFlowCount;

                        $absolutelyFlowMaximum = $isAvailableForDialCount * 4;
                        $relativeFlowMaximum = $this->getPredictiveRelativeFlowMax();

                        $newFlowCount = $actualFlowCount + 3;
                        $newFlowCount = ($newFlowCount > $absolutelyFlowMaximum) ? $absolutelyFlowMaximum : $newFlowCount;
                        $newFlowCount = ($newFlowCount > $relativeFlowMaximum) ? $relativeFlowMaximum : $newFlowCount;

                        if ($newFlowCount > $activePredictiveCallsCount) {
                            $newPredictiveFlowIsAllowed = true;
                        }
                    }
                }
            }

            // Если разрешение на выделение нового потока не удалось получить
            if (!$newPredictiveFlowIsAllowed) {
                return true;
            }

            // Немного корректируем время следующего звонка у лида
            $reserveSeconds = time() + 7;

            $leads->updateLeadProperty(
                $leadItem['Leads_ID'],
                [
                    'UF_CALL_DATE_TIME' => $reserveSeconds,
                ],
                'UIS_PREDICTIVE_CALL_SYSTEM_CORRECTION'
            );

            // Все проверки пройдены, отправляем лид на дозвон
            $this->sendLeadToDialerPredictiveFlow(
                [
                    'lead_data'    => $leadItem,
                    'staging_time' => time(),
                ]
            );

            sleep(1);
        }

        return true;
    }

    public function getPredictiveSuccessPercent() : int
    {
        $predictiveSuccessPercent = 70;

        EventManager::dispatch(Events::VATS_AFTER_PREDICTIVE_SUCCESS_PERCENT, $predictiveSuccessPercent);

        return $predictiveSuccessPercent;
    }

    /**
     * Возвращает максимально возможное кол-во предиктивных потоков для инстанса
     *
     * @return int
     */
    public function getPredictiveRelativeFlowMax()
    {
        $predictiveRelativeFlowMax = 100;

        EventManager::dispatch(Events::VATS_AFTER_PREDICTIVE_RELATIVE_FLOW_MAX, $predictiveRelativeFlowMax);

        return $predictiveRelativeFlowMax;
    }

    /**
     * Отправка в прозвон лидов
     *
     * @param $leadsArr
     *
     * @return true
     * @throws \Throwable
     */
    public function sendLeadToDialerPredictiveFlow($leadArr)
    {
        return RabbitProvider::send(RabbitQueue::DIALER_PREDICTIVE_FLOW, $leadArr);
    }

    /**
     * Предиктивный звонок по лиду
     * Определяем номер с которого будем звонить
     * Еще раз убедимся, что по лиду никто не звонит
     * Если звонок по лиду есть или пустой телефон то игнорируем задание
     * Начинаем дозвон
     *
     * @param $taskData
     *
     * @return true
     */
    public function dialerPredictiveFlow($taskData)
    {
        $stagingTime = $taskData['staging_time'];
        $leadArr = $taskData['lead_data'];

        // If source data is not correct
        if (empty($stagingTime) || empty($leadArr)) {
            return true;
        }

        // If staging time more than 30 seconds, doing nothing
        if ((time() - $stagingTime) >= 30) {
            return true;
        }

        // Определяем номер с которого будем звонить
        $leads = new Leads();

        $outgoingPhone = $this->getOutgoingOrderPhoneNumber(
            $leadArr['Leads_UF_ORDER'],
            $leadArr['Leads_ID'],
            $leadArr['Leads_UF_PHONE']
        );

        // Еще раз убедимся, что по лиду никто не звонит
        // Refactored
        $leadData = $leads->getLeadList(
            [
                'ID',
                'UF_UIS_CALL_ID',
            ],
            [
                'ID' => $leadArr['Leads_ID'],
            ],
            1
        );

        // Если звонок по лиду есть или пустой телефон то игнорируем задание
        if (!empty($leadData['Leads_UF_UIS_CALL_ID']) || !$outgoingPhone) {
            return true;
        }

        // Начинаем дозвон
        $this->startPredictiveCall($leadArr, $outgoingPhone);

        return true;
    }

    /**
     * Инициализация предиктивного звонка
     * Берем id сценарий в uis для предиктива
     * Инициализируем параметры для звонка
     * Отправляем запрос на инициализацию звонка
     * Получаем ID сессии звонка, если не удалось инициализировать звонок, останавливаем работу
     * Звонок начат, нужно создать запись в истории звонков
     * Автоматический сброс вызова, если клиент не отвечает
     * Если сотрудников больше нет онлайн, то готовимся сбросить вызов
     * Если ответа не последовало, то завершаем вызов и обрабатываем Лид статусом "Не дозвонились до клиента"
     *
     * @param $leadArr
     * @param $outgoingPhoneNumber
     *
     * @return bool
     * @throws SocketException
     * @throws \JsonException
     */
    public function startPredictiveCall($leadArr, SipEndpoint $outgoingPhone)
    {
        SocketService::sendLeadUpdateEvent(
            leadId: (int) $leadArr['Leads_ID'],
            eventCode: SocketEventRegistry::CALL_ALERTING,
            eventData: ['callSessionId' => 100]
        );

        $voxProvider = new VoxProvider();
        $leads = new Leads();
        $callResults = new Callresults();

        $outgoingPhoneNumber = $outgoingPhone->extractPhoneNumber();

        // Все проверки пройдены, начинаем прямой звонок на заданного сотрудника
        switch (InstanceHelper::getVatsProviderCode()) {
            case VatProvider::VOX:

                $callerEvent = [
                    'orderId' => (int) $leadArr['Leads_UF_ORDER'],
                    'callerIdForTransferPhone' => $outgoingPhoneNumber,
                ];

                EventManager::dispatch(Events::VATS_AFTER_CALLER_ID_FOR_TRANSFER_PHONE, $callerEvent);

                $CallScripts = new Callscripts();

                // TODO Ai is Allowed
                $callSessionData = $voxProvider->predictiveOutgoingCall(
                    leadPhone: (string) $leadArr['Leads_UF_PHONE'],
                    sipEndpoint:$outgoingPhone,
                    leadId: (int) $leadArr['Leads_ID'],
                    callerIdForTransferPhone: (string) $callerEvent['callerIdForTransferPhone'],
                    clientCallScript: $CallScripts->getPlainScriptText($leadArr['Orders_UF_CALL_CENTER_SCRIPT'], ['welcome', 'short', 'basic', 'additional']),
                    aiIsAllowed: $leadArr['Orders_aiPredictiveIsAllowed'],
                    aiPrompt: $leadArr['Orders_aiPrompt']
                );

                $callSessionId = $callSessionData['callSessionId'];
                $callManagementLink = $callSessionData['callManagementLink'];
                break;
            case VatProvider::UIS:
            case VatProvider::CG:
            default:
                // ID для предиктивного сценария в UIS
                $predictiveUisScenarioId = (int) (IO::readEnv('CONF_UIS_PREDICTIVE_SCENARIO_ID'));

                // Отправляем запрос на инициализацию звонка

                $res = UisApiProvider::startScenarioCall(
                    $outgoingPhoneNumber,
                    $leadArr['Leads_ID'],
                    $leadArr['Leads_UF_PHONE'],
                    $predictiveUisScenarioId
                );

                if (empty($res)) {
                    return false;
                }

                // Получаем ID сессии звонка, если не удалось инициализировать звонок, останавливаем работу
                $callSessionId = (int) ($res['data']['call_session_id']);
        }

        if (empty($callSessionId)) {
            return false;
        }

        $activePredictiveCallsCount = $this->getActivePredictiveCallsCount();
        $predictiveFlowNumber = $activePredictiveCallsCount + 1;

        // Звонок начат, нужно создать запись в истории звонков
        $callStatusRecordId = $callResults->createCallResult(
            [
                'sipEndpointId'           => $outgoingPhone->id,
                'UF_CLIENT_PHONE_NUMBER'    => $leadArr['Leads_UF_PHONE'],
                'UF_USER_ID'                => 0,
                'UF_CALL_SESSION_ID'        => $callSessionId,
                'UF_LEAD_ID'                => $leadArr['Leads_ID'],
                'UF_DIRECTION'              => 1,
                'UF_STATUS_CODE'            => '88888888888',
                'UF_IS_PREDICTIVE'          => 1, // Метка о том, что это предиктивный звонок
                'UF_PREDICTIVE_FLOW_NUMBER' => $predictiveFlowNumber,
            ]
        );

        if (empty($callStatusRecordId)) {
            return false;
        }

        $orders = new Orders();
        $callIntervals = new Callintervals();
        $linkedIntervalId = $orders->getLinkedIntervalId($leadArr['Leads_UF_ORDER']);
        if (!empty($linkedIntervalId)) {
            $intervalData = $callIntervals->getIntervalDataById($linkedIntervalId);
        } else {
            $intervalData = $callIntervals->getDefaultIntervalData();
        }

        $callIntervals = $intervalData['EXPLODED'];

        $leadsProps = [
            'UF_CALL_DATE_TIME'      => $this->calcNextCallTimeStamp(
                [],
                $callIntervals,
                $leadArr['Leads_UF_ORDER'],
                1500
            ),
            'UF_UIS_CALL_ID'         => $callSessionId,
            'UF_UIS_LAST_CALL_ID'    => $callSessionId,
            'UF_UIS_CALL_START_TIME' => time(),
            'UF_LOCAL_CALL_ID'       => $callStatusRecordId,
            'UF_LOCAL_LAST_CALL_ID'  => $callStatusRecordId,
        ];

        $leads->updateLeadProperty($leadArr['Leads_ID'], $leadsProps, 'UIS_START_PREDICTIVE_CALL');

        // Автоматический сброс вызова, если клиент не отвечает
        $notAnsweredCallStatus = '50000063670';
        $finishedCallStatus = '55555555555';
        $callStatusCode = $notAnsweredCallStatus;

        $breakQ = 0;
        [$minWaitingLimit, $maxWaitingLimit] = $this->getRaiseWaitingLimit();
        $backupWaitingTime = $this->getBackupWaitingLimit();

        for ($i = 0; $i < $maxWaitingLimit; $i++) {

            // Refactored
            $currentCallItem = $callResults->getCallResultsList(['UF_CLIENT_LEG_ID'], ['ID' => $callStatusRecordId], 1);

            if (!empty($currentCallItem['UF_CLIENT_LEG_ID'])) {
                return true;
            } else {
                $preparedForBreak = false;

                // Также проверяем состояние сотрудников
                $onlinePredictiveEmployees = $this->getOnlinePredictiveEmployees();

                // Если сотрудников больше нет онлайн, то готовимся сбросить вызов
                if (empty($onlinePredictiveEmployees)) {
                    $callStatusCode = $finishedCallStatus;
                    $preparedForBreak = true;
                } else {
                    $fullReadyPredictiveEmployees = $this->filterByOrderEmployees(
                        $onlinePredictiveEmployees,
                        $leadArr['Leads_UF_ORDER']
                    );

                    // Если нет онлайн сотрудников, способных обработать вызов, то готовимся сбросить вызов
                    if (empty($fullReadyPredictiveEmployees)) {
                        $callStatusCode = $finishedCallStatus;
                        $preparedForBreak = true;
                    } else {
                        // Определяем в каких состояниях у нас сейчас сотрудники
                        $haveAvailableForDial = false;
                        foreach ($fullReadyPredictiveEmployees as $employeeData) {
                            if ($employeeData['IS_AVAILABLE'] &&
                                !$employeeData['IS_ACTIVE_CALL'] ||
                                ((int) ($employeeData['UF_UIS_CALL_SESSION']) == (int) $callSessionId))
                            {
                                $haveAvailableForDial = true;
                                break;
                            }
                        }

                        if (!$haveAvailableForDial) {
                            $callStatusCode = ($i > $minWaitingLimit) ? $notAnsweredCallStatus : $finishedCallStatus;
                            $preparedForBreak = true;
                        }
                    }
                }

                if ($preparedForBreak) {
                    if ($breakQ > $backupWaitingTime) {
                        break;
                    }
                    $breakQ++;
                }
            }

            sleep(1);
        }

        /*
        * Если ответа не последовало, то завершаем вызов
        * и обрабатываем Лид статусом "Не дозвонились до клиента"
        */
        switch (InstanceHelper::getVatsProviderCode()) {
            case VatProvider::VOX:
                $voxProvider->finishPredictiveCall($callManagementLink);
            break;
            case VatProvider::UIS:
            case VatProvider::CG:
            default:
                UisApiProvider::finishCall($callSessionId);
        }

        $callResults->updateCallResult(
            $callStatusRecordId,
            [
                'UF_STATUS_CODE'    => $callStatusCode,
                'UF_LAST_EDITOR'    => 0,
                'UF_STATUS_COMMENT' => 'Автоматическая обработка',
            ]
        );

        $this->prepareLead(
            $leadArr['Leads_ID'],
            $leadArr['Leads_UF_ORDER'],
            'Автоматическая обработка лида',
            $callStatusCode
        );

        $this->afterSaveCallResultEvent($callStatusRecordId);

        $this->rabbitDialer(2);

        return true;
    }

    /**
     * Время дозвона пока клиент поднимет трубку.
     * Минимальное и максимальные значение
     *
     * @return array
     * */
    public function getRaiseWaitingLimit() : array
    {
        return [
            15,
            25
        ];
    }

    /**
     * Запасное время, которое мы даем сотрудникам для возвращения на линию
     *
     * @return int
     * */
    public function getBackupWaitingLimit() : int
    {
        return 5;
    }

    /**
     * Отправляет соообщение в Rabbit-очередь на выполнение задания afterSaveCallResult
     *
     * @param $callId
     *
     * @return true
     * @throws \Throwable
     */
    public function afterSaveCallResultEvent($callId)
    {
        return RabbitProvider::send(RabbitQueue::CALL_RESULT, ['callId' => $callId]);
    }

    /**
     * Делегирование предиктивного звонка
     * Проверяем, есть ли свободные сотрудники
     * Проверяем, есть ли сотрудники, закрепленные за заказом данного лида
     * Отправляем оператору актуальную информацию о его статусе по сокетам
     *
     * @json
     * @return true
     */
    public function delegatePredictiveCall()
    {
        $inputDataRaw = file_get_contents("php://input");

        $callResults = new Callresults();

        if (empty($inputDataRaw)) {
            $this->returnVatsResult(
                [
                    'returned_code' => 0, // Недостаточно информации для обработки
                ]
            );
        }

        $inputDataArr = json_decode($inputDataRaw, 1);
        switch (InstanceHelper::getVatsProviderCode()) {
            case VatProvider::VOX:
                $voxProvider = new VoxProvider();
                $predictiveCallData = $voxProvider->exportPredictiveCallData($inputDataArr);
            break;
            case VatProvider::UIS:
            case VatProvider::CG:
            default:
                $predictiveCallData = UisApiProvider::exportPredictiveCallData($inputDataArr);
        }

        if (empty($predictiveCallData['callSessionId']) || empty($predictiveCallData['callStartTs']) || empty($predictiveCallData['clearPhone'])) {
            $this->returnVatsResult(
                [
                    'returned_code' => 0, // Недостаточно информации для обработки
                ]
            );
        }

        $lastLeadArr = $this->searchLastLeadDataByPhoneNumber($predictiveCallData['clearPhone'], 'primary', null);

        if (empty($lastLeadArr)) {
            $this->returnVatsResult(
                [
                    'returned_code' => 2, // Лид не распознан
                ]
            );
        }

        //
        // Проверяем, есть ли свободные сотрудники
        $onlineReadyEmployees = $this->getOnlineReadyEmployees('predictive');
        if (empty($onlineReadyEmployees)) {
            $this->returnVatsResult(
                [
                    'returned_code' => 4,
                ]
            );
        }

        // Проверяем, есть ли сотрудники, закрепленные за заказом данного лида
        if (!empty($lastLeadArr['UF_ORDER'])) {
            // Проверяем, есть ли среди свободных сотрудников те, которые могут обработать данный лид
            $onlineReadyEmployees = $this->filterByOrderEmployees($onlineReadyEmployees, $lastLeadArr['UF_ORDER']);
            if (empty($onlineReadyEmployees)) {
                $this->returnVatsResult(
                    [
                        'returned_code' => 5,
                    ]
                );
            }
        }

        $callEmployeeData = $this->getNextEmployee($lastLeadArr['ID'], $onlineReadyEmployees);

        switch (InstanceHelper::getVatsProviderCode()) {
            case VatProvider::VOX:
                $callEmployeePhone = $callEmployeeData['UF_VOX_USER_NAME'];
            break;
            case VatProvider::UIS:
            case VatProvider::CG:
            default:
                $callEmployeePhone = UisApiProvider::getSipById($callEmployeeData['UF_UIS_ID']);
        }

        if (empty($callEmployeePhone)) {
            // Если не удалось определить сотрудника, которому нужно отдать вызов
            $this->returnVatsResult(
                [
                    'returned_code' => 6,
                ]
            );
        }

        // Обновляем запись в истории, добавляя сотрудника
        $callStatusEntityArr = $this->getCallStatusEntity($predictiveCallData['callSessionId']);

        $callStatusesHlEntityUpdResult = $callResults->updateCallResult(
            intval($callStatusEntityArr['ID']),
            ['UF_USER_ID' => $callEmployeeData['ID'],]
        );

        if (empty($callStatusesHlEntityUpdResult)) {
            // Не удалось обновить запись в истории дозвонов
            $this->returnVatsResult(
                [
                    'returned_code' => 7,
                ]
            );
        }

        // Проставляем идентификатор разговора оператору в пользовательское поле
        $this->updateCallCenterUserData(
            $callEmployeeData['ID'],
            [
                'UF_UIS_CALL_SESSION' => $predictiveCallData['callSessionId'],
            ]
        );

        // Отправляем оператору актуальную информацию о его статусе
        $this->sendEmployeeStatusBySocket($callEmployeeData['ID']);

        $this->returnVatsResult(
            [
                'phones'       => [
                    strval($callEmployeePhone),
                ],
                'message_name' => 'silent-is-gold.mp3',
            ]
        );

        return true;
    }

    /**
     * Возращаем инфу звонка по id сессии звонка
     *
     * @param $callSessionId
     *
     * @return array | bool
     */
    public function getCallStatusEntity($callSessionId)
    {
        if (empty($callSessionId)) {
            return false;
        }

        $callResults = new Callresults();

        // Refactored
        return $callResults->getCallResultsList(
            ['*'],
            [
                'UF_CALL_SESSION_ID' => $callSessionId,
            ],
            1
        );
    }

    /**
     * Получаем актуальную очередь
     * Берем рандомного свободного онлайн оператора и пытаемся сделать звонок по его первому лиду (который за ним
     * закреплен) Если все успешно инициализируем звонок
     *
     * @param bool $isStandAlone
     *
     * @api
     */
    public function dialer($isStandAlone = true)
    {
        $this->dialerCallSimulator();

        // Получаем актуальную очередь
        $dialerQueue = $this->getDialerQueue(
            null,
            false,
            [
                'current',
                'nearest_time',
                'another_time',
                'canceled_by_orders_call_status',
                'canceled_by_orders_time',
                'canceled_by_user_time',
                'current_predictive',
                'nearest_time_predictive',
                'another_time_predictive',
                'canceled_by_orders_call_status_predictive',
                'canceled_by_orders_time_predictive',
                'canceled_by_user_time_predictive',
                'canceled_by_user_time_predictive',
                'leads_by_id',
                'calls_by_lead',
                'call_center_users',
            ],
            100
        );

        $dialerQueueCallCenterUsers = $dialerQueue['call_center_users'];

        if (!empty($dialerQueueCallCenterUsers)) {

            $onlinePredictiveEmployees = $this->getOnlinePredictiveEmployees();

            $queueForPredictive = $infoPredictiveByOrderBuffer = [];
            if (!empty($onlinePredictiveEmployees)) {
                foreach ($dialerQueue['nearest_time_sliced'] as $leadArr) {
                    if (!isset($infoPredictiveByOrderBuffer[$leadArr['Leads_UF_ORDER']])) {
                        $predictiveIsAllowed = $this->orderPredictiveIsAllowed($leadArr['Leads_UF_ORDER']);
                        $infoPredictiveByOrderBuffer[$leadArr['Leads_UF_ORDER']] = $predictiveIsAllowed;
                    } else {
                        $predictiveIsAllowed = $infoPredictiveByOrderBuffer[$leadArr['Leads_UF_ORDER']];
                    }

                    if (!$predictiveIsAllowed) {
                        continue;
                    }

                    $fullReadyPredictiveEmployees = $this->filterByOrderEmployees(
                        $onlinePredictiveEmployees,
                        $leadArr['Leads_UF_ORDER']
                    );

                    // Если этим онлайн-операторам разрешено обрабатывать данный лид
                    if (!empty($fullReadyPredictiveEmployees)) {
                        $queueForPredictive[$leadArr['Leads_ID']] = $leadArr;
                    }
                }
            }

            /*
             * Если дошли до данного шага, значит это уже не предиктивный вызов
             * Проверяем, какие сотрудники КЦ сейчас онлайн в Лайнере
             * не в разговоре и не в поствызовной обработке,
             * а также в статусе "Доступен",
             * если никого нет, то останавливаем работу диалера
            */
            $onlineReadyEmployees = $this->getOnlineReadyEmployees('outgoing');

            shuffle($onlineReadyEmployees);

            if (!empty($onlineReadyEmployees)) {
                foreach ($onlineReadyEmployees as $employee) {
                    if (empty($dialerQueueCallCenterUsers[$employee['ID']])) {
                        continue;
                    }

                    foreach ($dialerQueueCallCenterUsers[$employee['ID']] as $leadId => $leadArr) {
                        if (isset($queueForPredictive[$leadId])) {
                            continue;
                        }

                        $orderPhone = $this->getOutgoingOrderPhoneNumber(
                            $leadArr['Leads_UF_ORDER'],
                            $leadId,
                            $leadArr['Leads_UF_PHONE']
                        );

                        $employeesForCall = $this->filterByOrderEmployees(
                            $onlineReadyEmployees,
                            $leadArr['Leads_UF_ORDER']
                        );

                        if (empty($employeesForCall) || !$orderPhone) {
                            continue;
                        }

                        $this->startCall($leadArr, $employeesForCall, $orderPhone);

                        break 2;
                    }
                }
            }

            if (!empty($queueForPredictive)) {
                $this->sendLeadsToDialerPredictiveManager($queueForPredictive);
            }
        }

        // Сохраняем очередь в шорт кеш
        $this->setCacheDialerQueue($dialerQueue);

        // Отправляем сигнал ресиверу прогнозов
        $futureScope = new Futurescope();
        $futureScope->foreCastSignal();

        return ($isStandAlone) ? IO::apiResult('', true) : true;
    }

    /**
     * Симулятор вызвова
     * Ищем сотрудников, готовых принять тестовый вызов
     * Инициируем звонок
     * Нагружаем сразу всех сотрудников в тренажере
     *
     * @return bool
     * @throws SocketException
     */
    public function dialerCallSimulator()
    {
        //
        // Ищем сотрудников, готовых принять тестовый вызов

        $onlineReadyEmployees = $this->getOnlineReadyEmployees('outgoing', true);
        shuffle($onlineReadyEmployees);

        //
        // Инициируем звонок
        // Если нет ни одного сотрудника, готового принять звонок, то останавливаем работу
        if (empty($onlineReadyEmployees)) {
            return false;
        }

        $phoneFieldCode = match (InstanceHelper::getVatsProviderCode()) {
            VatProvider::VOX => 'UF_VOX_USER_NAME',
            default => 'UF_UIS_ID',
        };

        // Нагружаем сразу всех сотрудников в тренажере
        foreach ($onlineReadyEmployees as $callEmployeeData) {
            if (empty($callEmployeeData[$phoneFieldCode])) {
                continue;
            }

            // Инициализируем параметры для звонка
            $callSessionId = rand(1111, 9999);

            // Проставляем идентификатор разговора оператору в пользовательское поле
            $this->updateCallCenterUserData(
                $callEmployeeData['ID'],
                [
                    'UF_UIS_CALL_SESSION' => $callSessionId,
                ]
            );

            $this->sendEmployeeStatusBySocket($callEmployeeData['ID']);

            // Отправляем запрос на поднятие трубки оператором
            SocketProvider::request(
                route: '/' . SocketEventRegistry::CALL_SIMULATOR_CALL . '/',
                method: HTTPMethod::POST,
                body: [
                    'channelId' => 'ch-' . $callEmployeeData['ID'],
                    'leadId'    => 1,
                ]
            );
        }

        return true;
    }

    /**
     * Очередь лидов на звонок
     * Выбираем все лиды, находящиеся в статусе "Новый"
     * Проверяем на график работы, статус заказов
     * Проверка на время работы операторов
     * Проверка на время перезвона для клиентов
     *
     * @param $leadId
     *
     * @return array
     */
    public function getDialerQueue($leadId = null, $withChartsData = false, $resultList = [], $sliceLeadsByOrder = 0)
    {
        $leads = new Leads();
        $callCenterGroups = new Callcentergroups();

        $getCallCenterGroupsList = $callCenterGroups->getCallCenterGroupsList();

        $resultLeadFilter = [
            Leads::DB_TABLE_NAME . ".UF_STATUS = 'primary'",
            Leads::DB_TABLE_NAME . ".UF_CALL_DATE_TIME > 0",
            Orders::DB_TABLE_NAME . ".ID > 0",
        ];

        if (!empty($leadId)) {
            if (is_array($leadId)) {
                $resultLeadFilter[] = Leads::DB_TABLE_NAME . ".ID IN (" . implode(',', $leadId) . ")";
            } else {
                $resultLeadFilter[] = Leads::DB_TABLE_NAME . ".ID = " . $leadId;
            }
        }

        $resultLeadSqlFilter = implode(' AND ', $resultLeadFilter);

        $leadsEntitySql = "
            SELECT 
                " . Leads::DB_TABLE_NAME . ".ID as Leads_ID,
                " . Leads::DB_TABLE_NAME . ".UF_DATE_CREATE as Leads_UF_DATE_CREATE,
                " . Leads::DB_TABLE_NAME . ".UF_ORDER as Leads_UF_ORDER,
                " . Leads::DB_TABLE_NAME . ".UF_STATUS as Leads_UF_STATUS,
                " . Leads::DB_TABLE_NAME . ".UF_CALL_DATE_TIME as Leads_UF_CALL_DATE_TIME,
                " . Leads::DB_TABLE_NAME . ".UF_PHONE as Leads_UF_PHONE,
                " . Leads::DB_TABLE_NAME . ".UF_USER_IP as Leads_UF_USER_IP,
                " . Leads::DB_TABLE_NAME . ".UF_UIS_CALL_ID as Leads_UF_UIS_CALL_ID,
                " . Leads::DB_TABLE_NAME . ".UF_CALL_PRIORITY as Leads_UF_CALL_PRIORITY,
                " . Leads::DB_TABLE_NAME . ".UF_CLIENT_UTC_OFFSET as Leads_UF_CLIENT_UTC_OFFSET,
                " . Leads::DB_TABLE_NAME . ".UF_CREATE_METHOD as Leads_UF_CREATE_METHOD,
                " . Leads::DB_TABLE_NAME . ".UF_LEAD_TYPE as Leads_UF_LEAD_TYPE,
                " . Leads::DB_TABLE_NAME . ".UF_IS_SECONDARY as Leads_UF_IS_SECONDARY,
                " . Orders::DB_TABLE_NAME . ".ID as Orders_ID,
                " . Orders::DB_TABLE_NAME . ".UF_CALL_INTERVALS as Orders_UF_CALL_INTERVALS,
                " . Orders::DB_TABLE_NAME . ".UF_NAME as Orders_UF_NAME,
                " . Orders::DB_TABLE_NAME . ".UF_STATUS as Orders_UF_STATUS,
                " . Orders::DB_TABLE_NAME . ".UF_CALL_IS_ALLOWED as Orders_UF_CALL_IS_ALLOWED,
                " . Orders::DB_TABLE_NAME . ".UF_WORK_TIME as Orders_UF_WORK_TIME,
                " . Orders::DB_TABLE_NAME . ".UF_CALL_CENTER_USERS as Orders_UF_CALL_CENTER_USERS,
                " . Orders::DB_TABLE_NAME . ".UF_CALL_CENTER_GROUPS as Orders_UF_CALL_CENTER_GROUPS,
                " . Orders::DB_TABLE_NAME . ".UF_PREDICTIVE_CALL_IS_ALLOWED as Orders_UF_PREDICTIVE_CALL_IS_ALLOWED,
                " . Orders::DB_TABLE_NAME . ".UF_ORDER_DIRECTION as Orders_UF_ORDER_DIRECTION,
                " . Orders::DB_TABLE_NAME . ".UF_IGNORE_CLIENT_TZ as Orders_UF_IGNORE_CLIENT_TZ,
                " . Orders::DB_TABLE_NAME . ".UF_USER as Orders_UF_USER,
                " . Orders::DB_TABLE_NAME . ".UF_CALL_CENTER_SCRIPT as Orders_UF_CALL_CENTER_SCRIPT,
                " . Orders::DB_TABLE_NAME . ".aiPredictiveIsAllowed as Orders_aiPredictiveIsAllowed,
                " . Orders::DB_TABLE_NAME . ".aiPrompt as Orders_aiPrompt,
                " . Callintervals::DB_TABLE_NAME . ".UF_INTERVALS as Orders_UF_INTERVALS
            FROM " . Leads::DB_TABLE_NAME . "
            LEFT JOIN " . Orders::DB_TABLE_NAME . " 
                on " . Orders::DB_TABLE_NAME . ".ID = " . Leads::DB_TABLE_NAME . ".UF_ORDER
            LEFT JOIN " . Callintervals::DB_TABLE_NAME . " 
                on " . Callintervals::DB_TABLE_NAME . ".ID = " . Orders::DB_TABLE_NAME . ".UF_CALL_INTERVALS
            WHERE " . $resultLeadSqlFilter . "
            ORDER BY " . Leads::DB_TABLE_NAME . ".UF_CALL_DATE_TIME ASC, " . Leads::DB_TABLE_NAME . ".ID DESC
        ";

        $leadsEntityResDb = DB::query($leadsEntitySql);

        $callsData = [];

        $availableResultListKeys = [
            'current',
            'current_predictive',
            'call_center_users',
            'canceled_by_orders_call_status',
            'canceled_by_orders_call_status_predictive',
            'canceled_by_orders_time',
            'canceled_by_orders_time_predictive',
            'canceled_by_user_time',
            'canceled_by_user_time_predictive',
            'nearest_time',
            'nearest_time_predictive',
            'another_time',
            'another_time_predictive',
            'leads_by_id',
            'calls_by_lead',
        ];

        foreach ($availableResultListKeys as $val) {
            if (empty($resultList) || in_array($val, $resultList)) {
                $callsData[$val] = [];
            }
        }

        $leadsIdsArr = [];

        $leadsEntityRes = [];

        while ($leadArr = $leadsEntityResDb->fetch()) {
            $leadsEntityRes[] = $leads->mutationsLeadData($leadArr);

            $leadsIdsArr[] = $leadArr['Leads_ID'];
        }

        if (isset($callsData['calls_by_lead']) && !empty($leadsIdsArr)) {
            // Получаем все, связанные с данными Лидами звонки
            $leadCallsEntityRes = (new Callresults())->getCallResultsList(
                [
                    'ID',
                    'UF_STATUS_CODE',
                    'UF_LEAD_ID',
                    'UF_DATE',
                ],
                [
                    'UF_LEAD_ID' => $leadsIdsArr,
                ],
            );

            foreach ($leadCallsEntityRes as $leadCallItem) {
                $callsData['calls_by_lead'][$leadCallItem['UF_LEAD_ID']][] = $leadCallItem;
            }
        }

        unset($leadsIdsArr);

        foreach ($leadsEntityRes as $leadArr) {
            $leadId = intval($leadArr['Leads_ID']);

            if (!empty($leadArr['Leads_UF_UIS_CALL_ID'])) {
                if (isset($callsData['leads_by_id'])) {
                    $callsData['leads_by_id'][$leadArr['Leads_ID']] = [
                        'data'   => $leadArr,
                        'status' => 'current',
                    ];
                }

                if (isset($callsData['current'])) {
                    $callsData['current'][] = $leadArr;
                }

                if (isset($callsData['current_predictive'])) {
                    if ($leadArr['Orders_UF_PREDICTIVE_CALL_IS_ALLOWED']) {
                        $callsData['current_predictive'][] = $leadArr;
                    }
                }

                continue;
            }

            if ($leadArr['Orders_UF_STATUS'] !== 'success') {
                continue;
            }

            if (!$leadArr['Orders_UF_CALL_IS_ALLOWED']) {
                if (isset($callsData['leads_by_id'])) {
                    $callsData['leads_by_id'][$leadArr['Leads_ID']] = [
                        'data'   => $leadArr,
                        'status' => 'canceled_by_orders_call_status',
                    ];
                }

                if (isset($callsData['canceled_by_orders_call_status'])) {
                    $callsData['canceled_by_orders_call_status'][] = $leadArr;
                }

                if (isset($callsData['canceled_by_orders_call_status_predictive'])) {
                    if ($leadArr['Orders_UF_PREDICTIVE_CALL_IS_ALLOWED']) {
                        $callsData['canceled_by_orders_call_status_predictive'][] = $leadArr;
                    }
                }

                continue;
            }

            if (!empty($leadArr['Orders_UF_WORK_TIME']) && !(new Orders())->isAllowedByTimeInterval(
                    $leadArr['Orders_UF_WORK_TIME'],
                    time(),
                    $leadArr['Orders_UF_USER']
                )) {
                if (isset($callsData['leads_by_id'])) {
                    $callsData['leads_by_id'][$leadArr['Leads_ID']] = [
                        'data'   => $leadArr,
                        'status' => 'canceled_by_orders_time',
                    ];
                }

                if (isset($callsData['canceled_by_orders_time'])) {
                    $callsData['canceled_by_orders_time'][] = $leadArr;
                }

                if (isset($callsData['canceled_by_orders_time_predictive'])) {
                    if ($leadArr['Orders_UF_PREDICTIVE_CALL_IS_ALLOWED']) {
                        $callsData['canceled_by_orders_time_predictive'][] = $leadArr;
                    }
                }

                continue;
            }

            if (!$leads->isAllowedByUserCondition(
                $leadArr['Leads_UF_CLIENT_UTC_OFFSET'],
                !empty($callsData['calls_by_lead'][$leadId]) && is_array(
                    $callsData['calls_by_lead'][$leadId]
                ) ? $callsData['calls_by_lead'][$leadId] : [],
                $leadArr
            )) {
                if (isset($callsData['leads_by_id'])) {
                    $callsData['leads_by_id'][$leadArr['Leads_ID']] = [
                        'data'   => $leadArr,
                        'status' => 'canceled_by_user_time',
                    ];
                }

                if (isset($callsData['canceled_by_user_time'])) {
                    $callsData['canceled_by_user_time'][] = $leadArr;
                }

                if (isset($callsData['canceled_by_user_time_predictive'])) {
                    if ($leadArr['Orders_UF_PREDICTIVE_CALL_IS_ALLOWED']) {
                        $callsData['canceled_by_user_time_predictive'][] = $leadArr;
                    }
                }

                continue;
            }

            if (time() >= intval($leadArr['Leads_UF_CALL_DATE_TIME'])) {
                if (isset($callsData['leads_by_id'])) {
                    $callsData['leads_by_id'][$leadArr['Leads_ID']] = [
                        'data'   => $leadArr,
                        'status' => 'nearest_time',
                    ];
                }

                $leadArr['UF_CALL_PRIORITY'] = (int) ($leadArr['Leads_UF_CALL_PRIORITY']);

                if (isset($callsData['nearest_time'])) {
                    $callsData['nearest_time'][] = $leadArr;
                }

                if (isset($callsData['nearest_time_predictive'])) {
                    if ($leadArr['Orders_UF_PREDICTIVE_CALL_IS_ALLOWED']) {
                        $callsData['nearest_time_predictive'][] = $leadArr;
                    }
                }
            } else {
                if (isset($callsData['leads_by_id'])) {
                    $callsData['leads_by_id'][$leadArr['Leads_ID']] = [
                        'data'   => $leadArr,
                        'status' => 'another_time',
                    ];
                }

                if (isset($callsData['another_time'])) {
                    $callsData['another_time'][] = $leadArr;
                }

                if (isset($callsData['another_time_predictive'])) {
                    if ($leadArr['Orders_UF_PREDICTIVE_CALL_IS_ALLOWED']) {
                        $callsData['another_time_predictive'][] = $leadArr;
                    }
                }
            }
        }

        // Сортируем массив лидов для ближайшего обзвона по приоритетам в порядке убывания
        if (!empty($callsData['nearest_time']) || isset($callsData['call_center_users'])) {
            if (!empty($callsData['nearest_time'])) {
                FunctionsHelper::sortArrayBy($callsData['nearest_time'], 'Leads_UF_CALL_PRIORITY desc');

                if ($sliceLeadsByOrder > 0) {
                    $slicedNearestTimeLeads = $leadsByOrderCounter = [];

                    foreach ($callsData['nearest_time'] as $leadArr) {
                        if (!isset($leadsByOrderCounter[$leadArr['Leads_UF_ORDER']])) {
                            $leadsByOrderCounter[$leadArr['Leads_UF_ORDER']] = 0;
                        }

                        $leadsByOrderCounter[$leadArr['Leads_UF_ORDER']]++;
                        if ($leadsByOrderCounter[$leadArr['Leads_UF_ORDER']] > $sliceLeadsByOrder) {
                            continue;
                        }

                        $slicedNearestTimeLeads[] = $leadArr;
                    }

                    $callsData['nearest_time_sliced'] = $slicedNearestTimeLeads;
                    unset($slicedNearestTimeLeads);
                }

                if (isset($callsData['call_center_users'])) {
                    foreach ($callsData['nearest_time'] as $leadArr) {
                        if (empty($leadArr['Orders_UF_CALL_CENTER_USERS']) && empty($leadArr['Orders_UF_CALL_CENTER_GROUPS'])) {
                            continue;
                        }

                        if (!empty($leadArr['Orders_UF_CALL_CENTER_USERS'])) {
                            $orderCallCenterUsers = explode(',', $leadArr['Orders_UF_CALL_CENTER_USERS']);
                            foreach ($orderCallCenterUsers as $userId) {
                                $callsData['call_center_users'][$userId][$leadArr['Leads_ID']] = $leadArr;
                            }
                        }

                        if (!empty($leadArr['Orders_UF_CALL_CENTER_GROUPS'])) {
                            $callCenterGroups = explode(',', $leadArr['Orders_UF_CALL_CENTER_GROUPS']);

                            $callCenterGroupsUsersIds = [];

                            if (!empty($callCenterGroups)) {
                                foreach ($callCenterGroups as $groupId) {
                                    if (!empty($getCallCenterGroupsList[$groupId]['OPERATORS_IDS'])) {
                                        $callCenterGroupsUsersIds = array_merge(
                                            $callCenterGroupsUsersIds,
                                            $getCallCenterGroupsList[$groupId]['OPERATORS_IDS']
                                        );
                                    }
                                }
                            }

                            foreach ($callCenterGroupsUsersIds as $userId) {
                                $callsData['call_center_users'][$userId][$leadArr['Leads_ID']] = $leadArr;
                            }
                        }
                    }
                }
            }
        }

        return $callsData;
    }

    /**
     * Проверяем заказ на возможность пердиктива
     *
     * @param $orderId
     *
     * @return bool
     */
    public function orderPredictiveIsAllowed($orderId)
    {
        $orders = new Orders();
        $orderData = $orders->getOrderDataById(
            $orderId,
            [
                'ID',
                'UF_PREDICTIVE_CALL_IS_ALLOWED',
            ]
        );

        return !empty($orderData['UF_PREDICTIVE_CALL_IS_ALLOWED']);
    }

    /**
     * Инициализация звонка в Лайнере
     * Если нет ни одного сотрудника, готового принять звонок, то останавливаем работу
     * Проверяем, разрешен ли вызов общим расписанием КЦ UIS
     * Определяем сотрудника, которому отдадим вызов
     * Все проверки пройдены, начинаем прямой звонок на заданного сотрудника
     * Инициализируем параметры для звонка
     * Получаем ID сессии звонка, если не удалось инициализировать звонок, останавливаем работу
     * Создаем запись в истории звонков
     *
     * @param $leadArr
     * @param $fullReadyEmployees
     * @param $phoneNumber
     *
     * @return bool
     * @throws SocketException
     */
    public function startCall($leadArr, $fullReadyEmployees, SipEndpoint $sipEndpoint)
    {
        $user = new User();
        $callResults = new Callresults();

        // Если нет ни одного сотрудника, готового принять звонок, то останавливаем работу
        if (empty($fullReadyEmployees)) {
            return false;
        }

        // Определяем сотрудника, которому отдадим вызов
        $callEmployeeData = $this->getNextEmployee($leadArr['Leads_ID'], $fullReadyEmployees);
        $localUserId = intval($callEmployeeData['ID']);

        if (empty($localUserId)) // Если не удалось определить сотрудника, останавливаем процесс инициализации звонка
        {
            return false;
        }

        $phoneNumber = $sipEndpoint->extractPhoneNumber();

        // Все проверки пройдены, начинаем прямой звонок на заданного сотрудника
        switch (InstanceHelper::getVatsProviderCode()) {
            case VatProvider::VOX:
                $voxUserName = $callEmployeeData['UF_VOX_USER_NAME'];
                if (empty($voxUserName)) {
                    return false;
                }

                $callerEvent = [
                    'orderId' => (int) $leadArr['Leads_UF_ORDER'],
                    'callerIdForTransferPhone' => $phoneNumber
                ];

                EventManager::dispatch(Events::VATS_AFTER_CALLER_ID_FOR_TRANSFER_PHONE, $callerEvent);

                $voxProvider = new VoxProvider();
                $callSessionId = $voxProvider->defaultOutgoingCall(
                    $leadArr['Leads_UF_PHONE'],
                    $sipEndpoint,
                    $leadArr['Leads_ID'],
                    $callEmployeeData['ID'],
                    $callEmployeeData['UF_VOX_USER_NAME'],
                    $callerEvent['callerIdForTransferPhone']
                );
            break;
            case VatProvider::UIS:
            case VatProvider::CG:
            default:

                $uisEmployeeId = (int) ($callEmployeeData['UF_UIS_ID']);
                if (empty($uisEmployeeId)) {
                    return false;
                }

                // Отправляем запрос на инициализацию звонка
                $res = UisApiProvider::startCall(
                    $phoneNumber,
                    $leadArr['Leads_ID'],
                    $leadArr['Leads_UF_PHONE'],
                    $uisEmployeeId
                );

                if (!empty($res['data']['call_session_id'])) {
                    $callSessionId = (int) ($res['data']['call_session_id']);
                }
        }

        if (empty($callSessionId)) {
            return false;
        }

        $callStatusRecordId = $callResults->createCallResult(
            [
                'sipEndpointId'        => $sipEndpoint->id,
                'UF_CLIENT_PHONE_NUMBER' => $leadArr['Leads_UF_PHONE'],
                'UF_USER_ID'             => $localUserId,
                'UF_CALL_SESSION_ID'     => $callSessionId,
                'UF_LEAD_ID'             => $leadArr['Leads_ID'],
                'UF_DIRECTION'           => 1,
                'UF_STATUS_CODE'         => '66666666666',
            ]
        );

        if (!empty($callStatusRecordId)) {
            // Интервалы возможных дозвонов
            $orders = new Orders();
            $callIntervals = new Callintervals();

            $linkedIntervalId = $orders->getLinkedIntervalId($leadArr['Leads_UF_ORDER']);
            if (!empty($linkedIntervalId)) {
                $intervalData = $callIntervals->getIntervalDataById($linkedIntervalId);
            } else {
                $intervalData = $callIntervals->getDefaultIntervalData();
            }

            $callIntervals = $intervalData['EXPLODED'];

            // Стираем запланированное время дозвона, и прописываем идентификатор сессии звонка в лид
            $leadsProps = [
                'UF_CALL_DATE_TIME'      => $this->calcNextCallTimeStamp(
                    [],
                    $callIntervals,
                    $leadArr['Leads_UF_ORDER'],
                    1500
                ),
                'UF_UIS_CALL_ID'         => $callSessionId,
                'UF_UIS_LAST_CALL_ID'    => $callSessionId,
                'UF_UIS_CALL_START_TIME' => time(),
                'UF_LOCAL_CALL_ID'       => $callStatusRecordId,
                'UF_LOCAL_LAST_CALL_ID'  => $callStatusRecordId,
            ];

            $this->getLeadsController()->updateLeadProperty($leadArr['Leads_ID'], $leadsProps, 'UIS_START_CALL');

            // Проставляем идентификатор разговора оператору в пользовательское поле
            $this->updateCallCenterUserData(
                $localUserId,
                [
                    'UF_UIS_CALL_SESSION' => $callSessionId,
                ]
            );

            $this->sendEmployeeStatusBySocket($localUserId);

            SocketService::sendLeadUpdateEvent(
                leadId: $leadArr['Leads_ID'],
                eventCode: SocketEventRegistry::CALL_ALERTING,
                eventData: ['callSessionId' => $callSessionId]
            );

            return true;
        }

        return false;
    }

    /**
     * Отправка в rabbit предиктив лидов для проверки на запуск в прозвон
     *
     * @param $leadsArr
     *
     * @return true
     * @throws \Throwable
     */
    public function sendLeadsToDialerPredictiveManager($leadsArr)
    {
        return RabbitProvider::send(RabbitQueue::DIALER_PREDICTIVE_MANAGER, $leadsArr);
    }

    /**
     * Сохраняет переданную очередь в шорт кеш
     *
     * @param $dialerQueue
     *
     * @return void
     */
    public function setCacheDialerQueue($dialerQueue)
    {
        $cacheHit = md5('dialerQueue');

        Cache::set($cacheHit, ['dialerQueue' => $dialerQueue], 10);
    }

    /**
     * Возвращает очередь из шорт-кеша
     *
     * @return array
     */
    public function getCacheDialerQueue()
    {
        $cacheHit = md5('dialerQueue');

        if ($cacheResult = Cache::get($cacheHit)) {
            if (isset($cacheResult['dialerQueue'])) {
                return $cacheResult['dialerQueue'];
            }
        }

        return [];
    }

    /**
     * Передача в rabbit сохранение записи звонка
     *
     * @throws \Throwable
     * @api
     */
    public function rabbitSaveCallRecord()
    {
        $input = file_get_contents("php://input");

        // Если тело запроса пустое, то останавливаем работу
        if (empty($input)) {
            return IO::jsonDeadResponse(Liner::t('Request body not passed'));
        }

        // Пакуем сообщение и отправляем
        $inputArr = json_decode($input, 1);
        RabbitProvider::send(RabbitQueue::CALL_RECORDS, $inputArr);

        return IO::jsonDeadResponse('', true);
    }

    /**
     * Сохранение записей разговора
     * Если это 3 запись будет попытка проверки на статус лида по продолжительности звонка
     *
     * @param array $data
     *
     * @tariffs
     * @return bool
     * @throws SocketException
     */
    public function saveCallRecord($data = []) : bool
    {
        $callRecords = new Callrecords();
        $callResults = new Callresults();

        if (empty($data)) {
            return false;
        }

        // Подготавливаем данные из уведомления
        switch (InstanceHelper::getVatsProviderCode()) {
            case VatProvider::VOX:
                $voxProvider = new VoxProvider();
                $callRecordData = $voxProvider->exportCallRecordData($data);
            break;
            case VatProvider::UIS:
            case VatProvider::CG:
            default:
                $callRecordData = UisApiProvider::exportCallRecordData($data);
        }

        // Если в уведомлении отсутствуют обязательные параметры, то останавливаем работу
        if (empty($callRecordData['callSessionId']) || empty($callRecordData['recordLink'])) {
            return false;
        }

        //
        // Если ID Лида не поступил, то стоит проверить, возможно это был входящий звонок
        if (empty($callRecordData['leadId'])) {
            // Refactored
            $leadLastCallItem = $callResults->getCallResultsList(
                ['*'],
                [
                    'UF_CALL_SESSION_ID' => $callRecordData['callSessionId'],
                ],
                1
            );

            // Запись в истории звонков не найдена, значит звонок не относится к Лайнеру
            if (empty($leadLastCallItem)) {
                return true;
            }

            if (!empty($leadLastCallItem['UF_LEAD_ID'])) {
                $callRecordData['leadId'] = $leadLastCallItem['UF_LEAD_ID'];
            }
        }

        if (empty($callRecordData['leadId']) && !empty($leadLastCallItem['UF_DIRECTION']) && $leadLastCallItem['UF_DIRECTION'] == 2) {
            // Получили запись разговора по проксированному вызову, которая нам не нужна
            // Подтверждаем сообщение и ничего не делаем
            return true;
        } elseif (empty($callRecordData['leadId'])) {
            // ID Лида не удалось определить, останавливаем работу
            return false;
        }

        // Корректируем ID лида
        $callRecordData['leadId'] = $this->correctLeadId($callRecordData['leadId']);

        // Готовим массив с описанием файла записи,
        // если сформировать массив не получилось, то останавливаем работу

        // Проверяем тариф
        // Проверяем общее время текущих записей разговора
        $totalRecordsTimeDuration = ceil($this->getTotalRecordsTimeSeconds() / 60);

        // Если тарифом запрещено сохранять файл, то ничего не делаем
        $recordFileName = null;

        if (!Plan::limitExceeded('mod_call_records', 'max_total_records_time_duration', $totalRecordsTimeDuration)) {
            // Пробуем сохранить файл
            try {
                $savedData = File::upload(
                    $callRecordData['callSessionId'] . '.mp3',
                    $callRecordData['recordLink'],
                    StorageScope::AUDIO_CALL_RECORD,
                );

                if(!empty($savedData['name'])) {
                    $recordFileName = $savedData['name'];
                }

            } catch (Exception $e) {
                // Skipping "empty" records...
                return $callRecordData['callDuration'] <= 5;
            }
        }

        // Сохраняем запись разговора
        $callRecordId = $callRecords->createCallRecord(
            [
                'UF_CALL_SESSION_ID'   => $callRecordData['callSessionId'],
                'UF_RECORD_FILE'       => $recordFileName,
                'UF_NOTIFICATION_TIME' => $callRecordData['notificationTimeStr'],
                'UF_CALL_DURATION'     => $callRecordData['callDuration'],
                'UF_IS_TRANSFER'       => $callRecordData['isTransfer'],
                'UF_LEAD_ID'           => $callRecordData['leadId'],
                'UF_USER_ID'           => $callRecordData['userId'],
            ]
        );

        $callRecordIsSaved = ($callRecordId);

        // Если в записи разговора отсутствует информация о сотруднике, то
        // полученный разговор был между клиентом и удаленным КЦ,
        // а это повод для проверки его длительности
        if ($callRecordData['isTransfer']) {
            $this->isTransfer($callRecordData['leadId'], $callRecordData['callSessionId']);
        }

        // Sending update by sockets
        if ($callRecordIsSaved) {
            SocketProvider::request(
                route: '/' .SocketEventRegistry::NEW_CALL_RECORD . '/',
                method: HTTPMethod::POST,
                body: [
                    'channelId' => 'lead-' . $callRecordData['leadId'],
                    'leadId' => $callRecordData['leadId']
                ]
            );

            SocketService::sendLeadUpdateEvent(
                leadId: $callRecordData['leadId'],
                eventCode: SocketEventRegistry::CALL_RECORD_SAVED,
                eventData: ['callSessionId' => $callRecordData['callSessionId']]
            );
        }

        $callRecords->createRecognitionTask($callRecordData['callSessionId'], $callRecordData['leadId']);

        return $callRecordIsSaved;
    }

    /**
     * Возращаем время в сек по всем записям
     *
     * @return int
     */
    private function getTotalRecordsTimeSeconds()
    {
        $callRecords = new Callrecords();

        $callRecordsRes = $callRecords->getCallRecordsList(['ID', 'UF_CALL_DURATION'], [], null, ['ID' => 'ASC']);

        $totalDuration = 0;
        foreach ($callRecordsRes as $callItem) {
            $totalDuration += $callItem['UF_CALL_DURATION'];
        }

        return $totalDuration;
    }

    /**
     * Функция завершает проверку лида при трансфере клиента по доп параметрам в заказе
     *
     * @param $leadId
     * @param $callSessionId
     *
     * @return void
     */
    public function isTransfer($leadId, $callSessionId)
    {
        $leadId = intval($leadId);

        $callSessionId = intval($callSessionId);

        $orders = new Orders();
        $leads = new Leads();
        $callRecords = new Callrecords();
        $callResults = new Callresults();

        if (empty($leadId) || empty($callSessionId)) {
            return;
        }

        $callRecordsRes = $callRecords->getCallRecordsList(
            ['ID', 'UF_CALL_DURATION'],
            [
                'UF_CALL_SESSION_ID' => $callSessionId,
                'UF_IS_TRANSFER'     => 1,
                'UF_LEAD_ID'         => $leadId,
            ],
            1,
        );

        if (empty($callRecordsRes)) {
            return;
        }

        // Находим запись в истории звонков, связанную с этой сессией
        // Refactored
        $callStatusRecordArr = $callResults->getCallResultsList(
            [
                'ID',
                'UF_CALL_SESSION_ID',
                'UF_STATUS_CODE',
            ],
            [
                'UF_CALL_SESSION_ID' => $callSessionId,
            ],
            1
        );

        $processedNotCompleteStatusesArr = [
            '66666666666', // Пост обработка не завершена
            '88888888888', // Не принят оператором
        ];

        if (empty($callStatusRecordArr) || in_array(
                (int) ($callStatusRecordArr['UF_STATUS_CODE']),
                $processedNotCompleteStatusesArr
            )) {
            return;
        }

        $callDuration = !empty(intval($callRecordsRes['UF_CALL_DURATION'])) ? intval(
            $callRecordsRes['UF_CALL_DURATION']
        ) : 0;

        // Достаем ID заказа из Лида, а также минимально возможную длительность разговора с клиента с КЦ
        // Refactored
        $leadArr = $leads->getLeadList(
            [
                'ID',
                'UF_STATUS',
                'UF_ORDER',
                'UF_PREPARE_IS_FINISHED',
            ],
            [
                'ID' => $leadId,
            ],
            1
        );

        if (empty($leadArr['UF_ORDER'])) {
            return;
        }

        $orderData = $orders->getOrderDataById(
            $leadArr['UF_ORDER'],
            [
                'ID',
                'UF_MIN_CLIENT_TIME',
            ]
        );

        $minClientTime = (!empty($orderData['UF_MIN_CLIENT_TIME'])) ? $orderData['UF_MIN_CLIENT_TIME'] : 0;

        if (!empty($minClientTime)) {
            $leadSuccessStatusValId = 'success';
            $leadPrimaryStatusValId = 'primary';

            if (($leadArr['UF_STATUS'] == $leadSuccessStatusValId) || ($leadArr['UF_STATUS'] == $leadPrimaryStatusValId)) {
                if ($callDuration < $minClientTime) {
                    /*
                    * Диалог продолжался не долго,
                    * будем считать, что он не дождался перевода на ОП
                    * делаем соответствующую пометку в истории
                    * и обрабатываем соответствующим образом лид
                    */
                    $callStatusXmlId = '22222222222';

                    $callStatusEntity = $this->getCallStatusEntity($callSessionId);

                    if (!empty($callStatusEntity)) {
                        $callStatusEntityId = intval($callStatusEntity['ID']);

                        $callStatusesHlEntityUpdResult = $callResults->updateCallResult(
                            $callStatusEntityId,
                            [
                                'UF_STATUS_CODE' => $callStatusXmlId,
                                'UF_LAST_EDITOR' => 0,
                            ]
                        );

                        if ($callStatusesHlEntityUpdResult) {
                            $this->prepareLead(
                                $leadId,
                                (int) ($leadArr['UF_ORDER']),
                                Liner::t('Automatic status adjustment'),
                                $callStatusXmlId,
                                true
                            );
                        }
                    }
                } elseif (($leadArr['UF_STATUS'] == $leadSuccessStatusValId) && ((int) ($leadArr['UF_PREPARE_IS_FINISHED']) !== 1)) {
                    $this->getLeadsController()->updateLeadProperty(
                        $leadArr['ID'],
                        ['UF_PREPARE_IS_FINISHED' => 1],
                        'UIS_SAVE_CALL_RECORD'
                    );
                }
            }
        }
    }

    /**
     * Функция для вызова cron, находим операторов которые не в сети и которые находятся в пост обработке и переводим
     * их в статус "нет на работе"
     *
     * @return bool
     */
    public function checkOperatorIsStatusPostCall()
    {
        $user = new User();

        $rsUsers = $user->getActiveCallCenterUsersMap();

        $employeeStatusMap = $this->getEmployeeStatusesMap(false);

        $phoneFieldCode = match (InstanceHelper::getVatsProviderCode()) {
            VatProvider::VOX => 'UF_VOX_USER_NAME',
            default => 'UF_UIS_ID',
        };

        foreach ($rsUsers as $userData) {
            $isOnline = SocketService::checkUserOnline(intval($userData['ID']));

            if ($isOnline || (empty($userData[$phoneFieldCode]) || $userData['BLOCKED'] == 'Y') || (!empty($userData['UF_TRAINING_IS_ENABLED']))) {
                continue;
            }

            $employeeStatusData = $this->getEmployeeStatus($userData);

            if ((int) $employeeStatusData['UF_UIS_ID'] != ($employeeStatusMap['post_call']) || time(
                ) - $userData['UF_STATUS_LAST_UPDATE'] < 5 * Time::MINUTE) {
                continue;
            }

            $this->changeEmployeeStatus($employeeStatusMap['not_at_work'], $userData['ID']);
        }

        return true;
    }

    /**
     * Возращаем дату начала последеней паузы пользователя
     *
     * @param string $userId
     */
    public function getStartDateBreak($userId)
    {
        $params = [
            'order'  => ['ID' => 'DESC'],
            'select' => ['*'],
            'limit'  => 1,
            'filter' => [
                'UF_EMPLOYEE' => $userId,
            ],
        ];

        $lastManualStatus = DB::getList(Callcenterstatushistory::DB_TABLE_NAME, $params)->fetch();

        if (!empty($lastManualStatus["UF_DATE"]) && is_string($lastManualStatus["UF_DATE"])) {
            $dateObj = new DateTime($lastManualStatus["UF_DATE"]);

            return $dateObj->format('Y-m-d H:i:s');
        }

        return '';
    }

    /**
     * Делаем проверку на выход в перерыв оператора
     * Смотрим если половина операторов уже на перерыве советуем ему выйти позже
     *
     * @api
     */
    public function checkOperatorsBreak()
    {
        $user = new User();

        $rsUsers = $user->getActiveCallCenterUsersMap();

        $employeeStatusMap = $this->getEmployeeStatusesMap(false);

        $quantityUsersIsOnline = 0;

        $quantityOfUsersOnBreak = 0;

        foreach ($rsUsers as $userData) {
            $isOnline = SocketService::checkUserOnline(intval($userData['ID']));

            $employeeStatusData = $this->getEmployeeStatus($userData);

            if ($isOnline && in_array(
                    $employeeStatusData['UF_UIS_ID'],
                    [
                        $employeeStatusMap['active_call'],
                        $employeeStatusMap['post_call'],
                        $employeeStatusMap['available'],
                    ]
                )) {
                $quantityUsersIsOnline++;
            }

            if ((int) ($employeeStatusData['UF_UIS_ID']) == $employeeStatusMap['break']) {
                $quantityOfUsersOnBreak++;
            }
        }

        $status = (($quantityUsersIsOnline <= 1 && $quantityOfUsersOnBreak === 0) || ($quantityUsersIsOnline > 1 && ($quantityUsersIsOnline - 1 - $quantityOfUsersOnBreak) * 100 / $quantityUsersIsOnline) >= 50) ? true : false;

        $message = ($status === true) ? '' : Liner::t(
            'Now it is undesirable to take a break, as there are few operators on the line. If possible, take a break a little later.'
        );

        return IO::jsonDeadResponse($message, $status);
    }

    public function getStaticInputData(): void
    {
        if (InstanceHelper::isVoxVatsProvider()) {
            (new VoxProvider())->getStaticInputData();
        }
    }

    /**
     * Входящий звонок
     * Проверка тариффа на входящие звонки
     * Проверка ключей от uis
     * Проверяем, разрешен ли входящий вызов на номер телефона, по которому звонят
     * Проверяем не звонит ли сам на себя
     * Проверяем, не находится ли номер телефона абонента в черном списке
     * Создаем запись в истории звонков
     * Проверяем, закреплен ли номер за конкретным заказом
     * Пытаемся найти Лид в статусе "Новый" с этим звонком
     * Если не найден Лид, в статусе "Новый", то пробуем найти "Целевой" лид
     * Если найден Лид в статусе "Целевой" то создаем с подбором
     * Если номер закреплен за заказом создаем лид под ним
     * Если после всех манипуляций выше, Лид опознать/создать не удалось, то завершаем вызов
     * Проверяем, есть ли свободные сотрудники и закрепленные за заказом и выбираем рандомного
     * Если пропущен входящий ставим время дозвона
     *
     * @tariffs
     * @api
     */
    protected function internalStartCall()
    {
        //
        // Проверка входящих, обязательных параметров

        $inputDataRaw = file_get_contents("php://input");

        $orders = new Orders();
        $callResults = new Callresults();

        if (!Plan::isAvailable('other_functions', 'params', 'incoming_calls_enabled')) {
            $this->returnVatsResult(
                [
                    'returned_code' => 8, // Входящие вызовы запрещены на данный номер
                ]
            );
        }

        if (empty($inputDataRaw)) {
            $this->returnVatsResult(
                [
                    'returned_code' => 0, // Недостаточно информации для обработки
                ]
            );
        }

        $inputDataArr = json_decode($inputDataRaw, 1);

        switch (InstanceHelper::getVatsProviderCode()) {
            case VatProvider::VOX:
                $voxProvider = new VoxProvider();
                $incomingCallData = $voxProvider->exportIncomingCallData($inputDataArr);
            break;
            case VatProvider::UIS:
            case VatProvider::CG:
            default:
                $incomingCallData = UisApiProvider::exportIncomingCallData($inputDataArr);
        }

        if (empty($incomingCallData['callSessionId']) || empty($incomingCallData['callStartTs']) || empty($incomingCallData['clearPhone']) || empty($incomingCallData['dialedPhone'])) {
            $this->returnVatsResult(
                [
                    'returned_code' => 0, // Недостаточно информации для обработки
                ]
            );
        }

        $sipEndpoint = null;

        switch ($incomingCallData['sipEndpointType']){
            case SipEndpointParams::PSTN :
                $sipEndpoint = SipEndpointRepository::findForPhone($incomingCallData['dialedPhone']);

                // Проверяем не звонит ли сам на себя
                if (SipEndpointRepository::isPhoneExists($incomingCallData['clearPhone'])) {
                    $this->returnVatsResult(
                        [
                            'returned_code' => 8, // Входящие вызовы запрещены на данный номер
                        ]
                    );
                }

                break;
            case SipEndpointParams::SIP_REG :
                $sipEndpoint = SipEndpointRepository::findSipReg($incomingCallData['sipId'], $incomingCallData['dialedPhone']);
                break;
        }

        //
        // Проверяем, разрешен ли входящий вызов на номер телефона, по которому звонят
        if (!$this->incomingIsAllowedByClearPhoneNumber($sipEndpoint)) {
            $this->returnVatsResult(
                [
                    'returned_code' => 8, // Входящие вызовы запрещены на данный номер
                ]
            );
        }

        //
        // Проверяем, не находится ли номер телефона абонента в черном списке
        if (BlockListService::isPhoneBlocked($incomingCallData['clearPhone'])) {
            $this->returnVatsResult(
                [
                    'returned_code' => 1, // Абонент в черном списке
                ]
            );
        }

        //
        // Достаем запись в истории звонков, если не существует - создаем
        // Refactored
        $callStatusRecordData = $callResults->getCallResultsList(
            ['ID'],
            [
                'UF_CALL_SESSION_ID' => $incomingCallData['callSessionId'],
                'UF_DIRECTION'       => 2,
            ],
            1,
        );

        if (!empty($callStatusRecordData['ID'])) {
            $callStatusRecordId = $callStatusRecordData['ID'];
        } else {
            $callStatusRecordId = $callResults->createCallResult(
                [
                    'sipEndpointId'        => $sipEndpoint->id,
                    'UF_CLIENT_PHONE_NUMBER' => $incomingCallData['clearPhone'],
                    'UF_CALL_SESSION_ID'     => $incomingCallData['callSessionId'],
                    'UF_DIRECTION'           => 2,
                    'UF_LAST_EDITOR'         => 0,
                    'UF_STATUS_COMMENT'      => Liner::t('Incoming call'),
                    'UF_STATUS_CODE'         => 88888888888,
                    'UF_CLIENT_LEG_ID'       => ($incomingCallData['clientLegId']) ? $incomingCallData['clientLegId'] : '',
                ]
            );
        }

        if (empty($callStatusRecordId)) {
            // Не удалось создать запись в истории дозвонов
            $this->returnVatsResult(
                [
                    'returned_code' => 7,
                ]
            );
        }

        //
        // Проверяем, закреплен ли номер за конкретным заказом
        $hardLinkedOrderId = $sipEndpoint && $sipEndpoint->orderId ? $sipEndpoint->orderId : null;

        //
        // Пытаемся найти Лид в статусе "Новый" с этим звонком,
        $lastLeadArr = $this->searchLastLeadDataByPhoneNumber(
            $incomingCallData['clearPhone'],
            'primary',
            $hardLinkedOrderId
        );

        if (empty($lastLeadArr)) {
            // Если лид не найден в статусе Новый, пытаемся найти Лид в обработке DiBot
            $diBotLeadArr = $this->searchLastLeadDataByPhoneNumber(
                $incomingCallData['clearPhone'],
                DiBotService::ACTIVE_LEAD_STATUS_CODE,
                $hardLinkedOrderId
            );
            if (!empty($diBotLeadArr) && $diBotIntegration = DiBotService::lastActiveIntegration($diBotLeadArr['ID'])) {
                DiBotService::stopLeadDialogue(
                    $diBotIntegration,
                    $diBotLeadArr['ID'],
                    DiBotService::RETURN_LEAD_STATUS_CODE,
                    Liner::t(
                        'The automated conversation with the lead has ended because the client called back on their own'
                    ),
                );

                $diBotLeadArr['UF_STATUS'] = DiBotService::RETURN_LEAD_STATUS_CODE; // Just for secondary sure ...
                $lastLeadArr = $diBotLeadArr;
            }
        }

        if (empty($lastLeadArr)) {
            // Если не найден Лид, в статусе "Новый", то пробуем найти "Целевой" лид
            $lastSuccessLeadArr = $this->searchLastLeadDataByPhoneNumber(
                $incomingCallData['clearPhone'],
                'success',
                null
            );
            // TODO

            if (!empty($lastSuccessLeadArr) && $lastSuccessLeadArr['ORDER']['UF_LEAD_TRANSFORM_IS_ENABLE']) {
                /*
                * Если найден Лид в статусе "Целевой",
                * то делаем магию
                */

                $orderDirection = $lastSuccessLeadArr['ORDER']['UF_ORDER_DIRECTION'];

                $defaultOrderId = $orders->getDefaultOrderIdForDirection($orderDirection);

                $defaultCityId = $orders->getDefaultCityIdForDirection($orderDirection);

                if (in_array(
                        $orderDirection,
                        ['cars', 'real_estate']
                    ) && !empty($defaultOrderId) && !empty($defaultCityId)) {
                    // Создаем новый Лид с типом "Подбор"

                    $selectionLeadProps = [
                        'UF_CITY'              => $defaultCityId,
                        'UF_LEAD_TYPE'         => 'selection',
                        'UF_STATUS'            => 'primary',
                        'UF_PHONE'             => $lastSuccessLeadArr['UF_PHONE'],
                        'UF_NAME'              => $lastSuccessLeadArr['UF_NAME'],
                        'UF_QUIZ_LOG'          => $lastSuccessLeadArr['UF_QUIZ_LOG'],
                        'UF_USER_IP'           => $lastSuccessLeadArr['UF_USER_IP'],
                        'UF_CLIENT_UTC_OFFSET' => $lastSuccessLeadArr['UF_CLIENT_UTC_OFFSET'],
                        'UF_IS_SECONDARY'      => 1,
                        'UF_PREVIOUS_LEAD'     => $lastSuccessLeadArr['ID'],
                        'UF_ORDER'             => $defaultOrderId,
                        'UF_FAIL_ORDERS'       => $lastSuccessLeadArr['ORDER']['ID'],
                        // В исключения заказа добавим заказ из предыдущего лида
                        'UF_CREATE_METHOD'     => 'portation',
                    ];

                    $selectionLeadId = $this->getLeadsController()->createLead(
                        $selectionLeadProps,
                        'UIS_INTERNAL_START_CALL'
                    );

                    if ($selectionLeadId) {
                        // Добавим в старый Лид ссылку на новый
                        $this->getLeadsController()->updateLeadProperty(
                            $lastSuccessLeadArr['ID'],
                            ['UF_NEXT_LEAD' => $selectionLeadId],
                            'UIS_INTERNAL_START_CALL'
                        );
                    }

                    // Будем считать, что поступивший звонок относится к новому лиду
                    $lastLeadArr = $this->searchLastLeadDataByPhoneNumber($incomingCallData['clearPhone']);
                }
            } elseif (!empty($hardLinkedOrderId)) {
                $orderData = $orders->getOrderDataById(
                    $hardLinkedOrderId,
                    [
                        'ID',
                        'UF_UNKNOWN_LEADS_ACTION',
                    ]
                );

                if (!empty($orderData['UF_UNKNOWN_LEADS_ACTION'])) {
                    switch ($orderData['UF_UNKNOWN_LEADS_ACTION']) {
                        case 'create_selection':
                            $newLeadType = 'selection';
                        break;
                        case 'create_straight':
                            $newLeadType = 'straight';
                        break;
                        case 'not':
                        default:
                            $newLeadType = '';
                    }

                    if (!empty($newLeadType)) {
                        $newOrderLeadProps = [
                            'UF_LEAD_TYPE'     => $newLeadType,
                            'UF_STATUS'        => 'primary',
                            'UF_PHONE'         => $incomingCallData['clearPhone'],
                            'UF_ORDER'         => $hardLinkedOrderId,
                            'UF_CREATE_METHOD' => 'incoming-call',
                            'UF_CLIENT_UTC_OFFSET' => Quiz::getUtcOffsetByPhoneOrIpV2($incomingCallData['clearPhone'], null)
                        ];

                        $this->getLeadsController()->createLead($newOrderLeadProps, 'UIS_INTERNAL_START_CALL');

                        $lastLeadArr = $this->searchLastLeadDataByPhoneNumber(
                            $incomingCallData['clearPhone'],
                            'primary',
                            $hardLinkedOrderId
                        );
                    }
                }
            }
        }

        //
        // Если после всех манипуляций выше, Лид опознать/создать не удалось, то завершаем вызов
        if (empty($lastLeadArr)) {
            $this->returnVatsResult(
                [
                    'returned_code' => 2, // Лид не распознан
                ]
            );
        }

        //
        // Обновляем запись в истории, добавляя ID Лида
        $callResults->updateCallResult($callStatusRecordId, ['UF_LEAD_ID' => $lastLeadArr['ID']]);

        //
        // Сразу же планируем перезвон по лиду, на случай, если не удастся принять входящий звонок
        $this->prepareLead(
            $lastLeadArr['ID'],
            (int) ($lastLeadArr['UF_ORDER']),
            Liner::t('Automatic lead processing'),
            88888888888
        );

        //
        // Проверяем, разрешены ли звонки на уровне заказа
        if (!$lastLeadArr['ORDER']['UF_CALL_IS_ALLOWED']) {
            $this->returnVatsResult(
                [
                    'returned_code' => 5, // Звонки на уровне заказа запрещены
                ]
            );
        }

        //
        //Проверяем рабочее время в заказе
        if (!$orders->isAllowedByTimeInterval($lastLeadArr['ORDER']['UF_WORK_TIME'], time(), $lastLeadArr['ORDER']['UF_USER'])) {
            $this->returnVatsResult([
                'returned_code' => 3, //Не рабочее время
            ]);
        }

        //
        //Проверяем выходные в заказе
        if (!$orders->isAllowedByHolidaysInterval($lastLeadArr['ORDER']['UF_HOLIDAYS'], new DateTime())) {
            $this->returnVatsResult([
                'returned_code' => 3, //Не рабочее время
            ]);
        }

        $holdSoundPayload = [
            'lastLeadArr' => $lastLeadArr,
            'customBusyDelay' => ''
        ];

        EventManager::dispatch(Events::VATS_AFTER_DEFINE_INCOMING_BUSY_DELAY_SOUND, $holdSoundPayload);

        //
        // Проверяем, есть ли свободные сотрудники
        $onlineReadyEmployees = $this->getOnlineReadyEmployees('incoming');
        if (empty($onlineReadyEmployees)) {
            $this->preparePotentialEmployeeForIncoming($lastLeadArr['UF_ORDER']);
            $vatsResult = [
                'returned_code' => 4, // Нет свободных сотрудников
            ];
            if (InstanceHelper::isVoxVatsProvider() && !empty($holdSoundPayload['customBusyDelay'])) {
                $vatsResult['custom_busy_delay'] = $holdSoundPayload['customBusyDelay'];
            }
            $this->returnVatsResult($vatsResult);
        }

        //
        // Проверяем, есть ли среди свободных сотрудников те, которые могут обработать данный лид
        $onlineReadyEmployees = $this->filterByOrderEmployees($onlineReadyEmployees, $lastLeadArr['UF_ORDER']);
        if (empty($onlineReadyEmployees)) {
            $this->preparePotentialEmployeeForIncoming($lastLeadArr['UF_ORDER']);
            $vatsResult = [
                'returned_code' => 5, // Нет свободных сотрудников
            ];
            if (InstanceHelper::isVoxVatsProvider() && !empty($holdSoundPayload['customBusyDelay'])) {
                $vatsResult['custom_busy_delay'] = $holdSoundPayload['customBusyDelay'];
            }
            $this->returnVatsResult($vatsResult);
        }

        $callEmployeeData = $this->getNextEmployee($lastLeadArr['ID'], $onlineReadyEmployees);

        $callEmployeePhone = match (InstanceHelper::getVatsProviderCode()) {
            VatProvider::VOX => $callEmployeeData['UF_VOX_USER_NAME'],
            default => UisApiProvider::getSipById($callEmployeeData['UF_UIS_ID']),
        };

        if (empty($callEmployeePhone)) {
            // Если не удалось определить сотрудника, которому нужно отдать вызов
            $this->preparePotentialEmployeeForIncoming($lastLeadArr['UF_ORDER']);
            $vatsResult = [
                'returned_code' => 6, // Нет свободных сотрудников
            ];
            if (InstanceHelper::isVoxVatsProvider() && !empty($holdSoundPayload['customBusyDelay'])) {
                $vatsResult['custom_busy_delay'] = $holdSoundPayload['customBusyDelay'];
            }
            $this->returnVatsResult($vatsResult);
        }

        //
        // Все проверки пройдены, инициируем звонок в Лайнере

        // Обновляем запись в истории, добавляя сотрудника
        $callStatusesHlEntityUpdResult = $callResults->updateCallResult(
            $callStatusRecordId,
            ['UF_USER_ID' => $callEmployeeData['ID'],]
        );

        if (empty($callStatusesHlEntityUpdResult)) {
            $this->preparePotentialEmployeeForIncoming($lastLeadArr['UF_ORDER']);
            // Не удалось обновить запись в истории дозвонов
            $vatsResult = [
                'returned_code' => 7, // Нет свободных сотрудников
            ];
            if (InstanceHelper::isVoxVatsProvider() && !empty($holdSoundPayload['customBusyDelay'])) {
                $vatsResult['custom_busy_delay'] = $holdSoundPayload['customBusyDelay'];
            }
            $this->returnVatsResult($vatsResult);
        }

        // Стираем запланированное время дозвона, и прописываем идентификатор сессии звонка в лид
        $leadsProps = [
            'UF_UIS_CALL_ID'         => $incomingCallData['callSessionId'],
            'UF_UIS_LAST_CALL_ID'    => $incomingCallData['callSessionId'],
            'UF_UIS_CALL_START_TIME' => $incomingCallData['callStartTs'],
            'UF_LOCAL_CALL_ID'       => $callStatusRecordId,
            'UF_LOCAL_LAST_CALL_ID'  => $callStatusRecordId,
        ];

        $updateRes = $this->getLeadsController()->updateLeadProperty(
            $lastLeadArr['ID'],
            $leadsProps,
            'UIS_INTERNAL_START_CALL'
        );

        // Проставляем идентификатор разговора оператору в пользовательское поле
        $this->updateCallCenterUserData(
            $callEmployeeData['ID'],
            [
                'UF_UIS_CALL_SESSION' => $incomingCallData['callSessionId'],
            ]
        );

        // Отправляем оператору актуальную информацию о его статусе
        $this->sendEmployeeStatusBySocket($callEmployeeData['ID']);

        switch (InstanceHelper::getVatsProviderCode()) {
            case VatProvider::VOX:

                $callerEvent = [
                    'orderId' => (int) $lastLeadArr['UF_ORDER'],
                    'callerIdForTransferPhone' => (string) $incomingCallData['dialedPhone'],
                ];

                EventManager::dispatch(Events::VATS_AFTER_CALLER_ID_FOR_TRANSFER_PHONE, $callerEvent);

                $returnVatsResult = [
                    'phones'       => [
                        strval($callEmployeePhone),
                    ],
                    'dialed_number' => $callerEvent['callerIdForTransferPhone']
                ];
            break;
            case VatProvider::UIS:
            case VatProvider::CG:
            default:
                $returnVatsResult = [
                    'phones'       => [
                        strval($callEmployeePhone),
                    ],
                    'message_name' => 'phone-beeps.mp3',
                ];
        }

        LogService::info(
            [
                '$incomingCallData' => $incomingCallData,
                '$lastLeadArr'      => $lastLeadArr,
                '$leadsProps'       => $leadsProps,
                '$updateRes'        => $updateRes,
                '$callEmployeeData' => $callEmployeeData,
                '$returnVatsResult' => $returnVatsResult,
            ],
            [
                'INTERNAL_START_CALL',
            ]
        );

        // Отправляем команду в UIS на переадресацию звонка на данного оператора
        $this->returnVatsResult($returnVatsResult);
    }

    public function returnVatsResult($data)
    {
        header('Content-Type: application/json');
        echo json_encode($data);
        exit();
    }

    //
    // Regular tasks methods

    /**
     * Поиск последнего лида по телефону
     *
     * @param        $phoneNumber
     * @param string $statusXmlId
     * @param ?int   $orderId
     *
     * @return array
     */
    public function searchLastLeadDataByPhoneNumber($phoneNumber, $statusXmlId = 'primary', $orderId = null)
    {
        $orders = new Orders();
        $leads = new Leads();

        $leadsFilter = [
            'UF_PHONE'  => $phoneNumber,
            'UF_STATUS' => $statusXmlId,
        ];

        if (!empty($orderId)) {
            $leadsFilter['UF_ORDER'] = $orderId;
        }

        // Refactored
        $leadArr = $leads->getLeadList(
            [
                'ID',
                'UF_STATUS',
                'UF_LEAD_TYPE',
                'UF_ORDER',
                'UF_UIS_CALL_ID',
                'UF_UIS_CALL_START_TIME',
                'UF_UIS_LAST_CALL_ID',
                'UF_PHONE',
                'UF_NAME',
                'UF_QUIZ_LOG',
                'UF_USER_IP',
                'UF_CLIENT_UTC_OFFSET',
            ],
            $leadsFilter,
            1
        );

        if (!empty($leadArr['UF_ORDER'])) {
            $orderData = $orders->getOrderDataById(
                $leadArr['UF_ORDER'],
                [
                    'ID',
                    'UF_NAME',
                    'UF_LEAD_TRANSFORM_IS_ENABLE',
                    'UF_CALL_IS_ALLOWED',
                    'UF_ORDER_DIRECTION',
                    'UF_WORK_TIME',
                    'UF_HOLIDAYS',
                    'UF_USER',
                ]
            );

            if (!empty($orderData)) {
                $leadArr['ORDER'] = $orderData;
            }
        }

        return $leadArr;
    }

    /**
     * Возращаем контроллер Leads
     *
     * @return Leads
     */
    public function getLeadsController()
    {
        return new Leads();
    }

    /**
     * Обработка лида в зависимости от статуса оператора
     * already-success ОП перезвонил клиенту самостоятельно можно не ждать других обработчиков
     * dark Успешный лид, нужно подтверждать 3 записью
     * fail-straight происходит браковка лида
     * Все остальные слуачаи проверка что не равен Просьба перезвонить
     * Поднимаем интервалы
     * Закрываем лид если превышен лимит дозвон
     * Назначем время следующего звонка если с лидом все ок
     *
     * @param      $leadId
     * @param      $orderId
     * @param      $comment
     * @param      $callStatusXmlId
     * @param bool $leadPrepareIsFinished (если все обработки завершены по лиду ставим true)
     */
    public function prepareLead($leadId, $orderId, $comment, $callStatusXmlId, $leadPrepareIsFinished = false)
    {
        $payload = compact('leadId', 'orderId', 'comment', 'callStatusXmlId', 'leadPrepareIsFinished');
        EventManager::dispatch(Events::VATS_BEFORE_PREPARE_LEAD, $payload);
        extract($payload);

        $props = [];

        $callIntervals = new Callintervals();
        $orders = new Orders();
        $leads = new Leads();

        $statusesMap = $this->getStatusesMap();

        switch ($statusesMap[$callStatusXmlId]) {
            case 'already-success':
                // ОП перезвонил клиенту самостоятельно
                $leads->firstApprove($leadId, $orderId, 1);
            break;
            case 'dark':
                // Успешный лид, нужно подтверждать
                $leads->firstApprove($leadId, $orderId, $leadPrepareIsFinished);
            break;
            case 'danger':
                // Плохой лид, нужно браковать
                $leads->firstCancel($leadId, $comment);
            break;
            case 'fail-straight':
                // Плохой лид, нужно браковать
                $leads->firstCancel($leadId, $comment, 'fail-straight');
            break;
            default:
                // Работа над лидом не завершена, с клиентом не поговорили

                // Обновляем статус лида, согласно карте статусов
                $props['UF_STATUS'] = $statusesMap[$callStatusXmlId];

                // Перед тем как запланировать звонок убедимся, что звонок не попадает под исключения
                if ($callStatusXmlId != '50000063681') {
                    // Интервалы возможных дозвонов
                    $linkedIntervalId = $orders->getLinkedIntervalId($orderId);
                    if (!empty($linkedIntervalId)) {
                        $intervalData = $callIntervals->getIntervalDataById($linkedIntervalId);
                    } else {
                        $intervalData = $callIntervals->getDefaultIntervalData();
                    }

                    $callIntervals = $intervalData['EXPLODED'];

                    switch (intval($callStatusXmlId)) {
                        case '55555555555':
                            $props['UF_CALL_DATE_TIME'] = $this->calcNextCallTimeStamp(
                                [],
                                $callIntervals,
                                $orderId,
                                300
                            );
                            break;
                        /*
                        Если клиент позвонил сам или поговорил с ОП слишком мало
                        или не дождался перевода на КЦ,
                        то планируем следующий звонок в максимально
                        близкое время, без учета интервалов дозвонов
                        */
                        case '88888888888':
                        // Если был входящий звонок, то ставим приоритет лиду
                        $props['UF_CALL_PRIORITY'] = $leads->calcCallPriority($orderId, 15);
                        $props['UF_CALL_DATE_TIME'] = $this->calcNextCallTimeStamp([], $callIntervals, $orderId, 300);
                            break;
                        case '22222222222':
                        case '50000063675':
                            $callbackTimeoutWhenNotCallingTheSd = intval(
                                $orders->getOrdersListNew(
                                    ['sdCallbackDelay'],
                                    ['ID' => $orderId],
                                    1
                                )['sdCallbackDelay'] ?? 0
                            );

                            if ($callbackTimeoutWhenNotCallingTheSd == -1) {
                                $props['UF_CALL_DATE_TIME'] = $this->calcNextCallTimeStamp(
                                    $this->getHistoryByLead($leadId, true, $intervalData['UF_RESET_ATTEMPTS'], $callStatusXmlId),
                                    $callIntervals,
                                    $orderId
                                );
                            } else {
                                $props['UF_CALL_DATE_TIME'] = $this->calcNextCallTimeStamp(
                                    [],
                                    $callIntervals,
                                    $orderId,
                                    $callbackTimeoutWhenNotCallingTheSd
                                );
                            }
                            break;
                        /*
                        * Если звонок закрыли статусом "Не дозвонились до КЦ"
                        * то планируем время перезвона через 25 минут
                        */
                        case '50000063682':
                            $props['UF_CALL_PRIORITY'] = $leads->calcCallPriority($orderId, 15);
                            $props['UF_CALL_DATE_TIME'] = $this->calcNextCallTimeStamp([], $callIntervals, $orderId, 1250);
                            break;
                        /*
                        * Если клиент бросил трукбу, то делаем кастомный оффсет в 7200 cек (2 часа)
                        */
                        case '50000063673':
                            $preparedTimeStamp = $this->calcNextCallTimeStamp([], $callIntervals, $orderId);

                            if ($preparedTimeStamp - time() <= Time::HOUR * 2) {
                                $props['UF_CALL_DATE_TIME'] = $this->calcNextCallTimeStamp(
                                    [],
                                    $callIntervals,
                                    $orderId,
                                    Time::HOUR * 2
                                );
                            }
                            break;
                        /*
                        * Если клиенту Неудобно, то делаем кастомный оффсет в 7200 cек (2 часа)
                        */
                        case '50000063700':
                            $props['UF_CALL_DATE_TIME'] = $this->calcNextCallTimeStamp([], $callIntervals, $orderId, Time::HOUR * 2);
                            break;
                        /*
                        Если упущен телефонией,
                        то проверим количество упущенных телефонией звонков подряд,
                        если их меньше допустимого количества (3), то
                        следующий дозвон попробуем сделать через 120 сек.
                        */
                        case '77777777777':
                            // История всех дозвонов, включая исключения, по данному лиду
                            $leadHistory = $this->getHistoryByLead($leadId, true, false, $callStatusXmlId);
                            if (!empty($leadHistory) && (count(
                                        $leadHistory
                                    ) >= 3) && ($leadHistory[0]['UF_STATUS_CODE'] == '77777777777') && ($leadHistory[0]['UF_STATUS_CODE'] == $leadHistory[1]['UF_STATUS_CODE']) && ($leadHistory[0]['UF_STATUS_CODE'] == $leadHistory[2]['UF_STATUS_CODE'])) {
                                /*
                                Последние 3 звонка были Упущены телефонией
                                нет смысла звонить больше
                                ставим статус браковки (Лимит дозвонов)
                                */
                                $props['UF_STATUS'] = 'call-limit';
                                $props['UF_PREPARE_IS_FINISHED'] = 1;
                            } else {
                                // Все в порядке, попробуем дозвониться еще разок, через 120 секунд
                                $props['UF_CALL_DATE_TIME'] = $this->calcNextCallTimeStamp(
                                    [],
                                    $callIntervals,
                                    $orderId,
                                    300
                                );
                            }
                            break;
                        /*
                        Обычные ситуации отрабатывают согласно логике интервалов
                        Если следующий звонок еще не запланирован, то планируем по интервалам
                        */
                        default:

                            $callStatusesList = new Callstatuseslist();

                            $resetStatusesArr = $callStatusesList->getResetAttemptsStatusesCode();

                            // История всех нормальных дозвонов по данному лиду
                            $leadHistory = $this->getHistoryByLead($leadId, false, $intervalData['UF_RESET_ATTEMPTS'], $callStatusXmlId);

                            $leadHistoryGoodAttemptsCount = 0;
                            foreach ($leadHistory as $item) {
                                if (!in_array($item['UF_STATUS_CODE'], $resetStatusesArr)) {
                                    $leadHistoryGoodAttemptsCount++;
                                }
                            }

                            $maxCallIntervalsCount = $this->calcEffectiveIntervalCount($intervalData, $leadHistory);

                            $isBrokenCall = $this->isBrokenCall($leadHistory);

                            if (($leadHistoryGoodAttemptsCount < $maxCallIntervalsCount) && !$isBrokenCall) {
                                // Количество попыток меньше лимита
                                $nextCallTimeStamp = $this->calcNextCallTimeStamp($leadHistory, $callIntervals, $orderId);
                                if ($nextCallTimeStamp) {
                                    $props['UF_CALL_DATE_TIME'] = $nextCallTimeStamp;
                                }

                                // Приоритизация следующих попыток
                                switch ($leadHistoryGoodAttemptsCount) {
                                    case 1:
                                        $tmpCallPriority = 6;
                                    break;
                                    case 2:
                                        $tmpCallPriority = 4;
                                    break;
                                    case 3:
                                        $tmpCallPriority = 3;
                                    break;
                                    case 4:
                                        $tmpCallPriority = 2;
                                    break;
                                    default:
                                        $tmpCallPriority = 0;
                                }

                                $props['UF_CALL_PRIORITY'] = $leads->calcCallPriority($orderId, $tmpCallPriority);
                            } elseif (!in_array(
                                $callStatusXmlId,
                                array_merge(
                                    ['66666666666'],
                                    $callStatusesList->getIgnoreStatusCode(),
                                    $callStatusesList->getResetAttemptsStatusesCode()
                                )
                            )) {
                                $props['UF_STATUS'] = 'call-limit';
                                $props['UF_PREPARE_IS_FINISHED'] = 1;
                            }
                    }
                }
        }

        // Обновляем лид
        $this->getLeadsController()->updateLeadProperty($leadId, $props, 'UIS_PREPARE_LEAD');

        return [
            'is_approved' => ($statusesMap[$callStatusXmlId] == 'dark'),
            'is_canceled' => ($statusesMap[$callStatusXmlId] == 'danger'),
            'is_recall'   => !empty($nextCallTimeStamp),
        ];;
    }

    /**
     * Назначаем лиду время следующего звонка
     * Если звонков нет прибавляем первый интервал + $customOffset
     * Если звонки есть прибавляем к прошлому звонку время по следующему интервалу
     * Если передан заказ, достаем его график работы
     *
     * @param array  $leadHistory
     * @param array  $callIntervals
     * @param string $orderId
     * @param int    $customOffset
     *
     * @return int
     */
    public function calcNextCallTimeStamp($leadHistory, $callIntervals, $orderId = '', $customOffset = 0)
    {
        if (empty($leadHistory)) {
            return time() + $callIntervals[0] + $customOffset;
        }

        $historyCount = count($leadHistory);

        $lastCallTimeStamp = $leadHistory[$historyCount - 1]['UF_DATE']->format('U');

        // Наполняем массив отсутствующими интервалами
        $copyKey = 1;
        while ($historyCount >= count($callIntervals)) {
            $callIntervals[] = $callIntervals[$copyKey];
            $copyKey = ($copyKey + 1) % count($callIntervals);
        }

        $nextCallInterval = $callIntervals[$historyCount] * 60;

        $resultCallTimeStamp = $lastCallTimeStamp + $nextCallInterval;

        if (!empty($orderId)) {
            $nextCallDateTimeObj = DateTime::createFromFormat('U', $resultCallTimeStamp);

            // У Лида есть заказ, достаем его график работы
            $orders = new Orders();
            $orderData = $orders->getOrderDataById(
                $orderId,
                [
                    'UF_HOLIDAYS',
                    'UF_WORK_TIME',
                ]
            );

            $nextCallDateTimeObj = $this->getNearestCallDateTime($orderData, $nextCallDateTimeObj);

            $resultCallTimeStamp = $nextCallDateTimeObj->format('U');
        }

        return $resultCallTimeStamp + $customOffset;
    }

    /**
     * Проверяем на праздничные дни и выходные настройки в заказе для следующего звонка
     * Функция содержит рекурсию
     *
     * @param array  $orderData
     * @param object $nextCallDateTimeObj
     *
     * @return object
     */
    public function getNearestCallDateTime($orderData, $nextCallDateTimeObj)
    {
        $nextCallDateTimeObj->modify('+1 seconds');

        if (!empty($orderData['HOLIDAYS']) && in_array($nextCallDateTimeObj->format('d.m.Y'), $orderData['HOLIDAYS'])) {
            $nextCallDateTimeObj->modify('+ 1 min');
            $nextCallDateTimeObj = $this->getNearestCallDateTime($orderData, $nextCallDateTimeObj);
        }

        if (!empty($orderData['UF_WORK_TIME'])) {
            $workTime = json_decode($orderData['UF_WORK_TIME'], 1);
            if (!empty($workTime[date('N')])) {
                $timeArr = $workTime[date('N')];
                $timeStartObj = Moment::create(
                    dateTime: $nextCallDateTimeObj->format('d.m.Y') . ' ' . $timeArr[0],
                    fromTz: TZ::LOCAL,
                );
                $timeEndObj = Moment::create(
                    dateTime: $nextCallDateTimeObj->format('d.m.Y') . ' ' . $timeArr[1],
                    fromTz: TZ::LOCAL,
                );
                if (($nextCallDateTimeObj->format('U') < $timeStartObj->format('U')) || ($nextCallDateTimeObj->format(
                            'U'
                        ) > $timeEndObj->format('U'))) {
                    $nextCallDateTimeObj->modify('+ 1 min');
                    $nextCallDateTimeObj = $this->getNearestCallDateTime($orderData, $nextCallDateTimeObj);
                }
            }
        }

        return $nextCallDateTimeObj;
    }

    /**
     * История звонков по лиду
     * Поднимаем все записи звонков
     * Но не учитываем следующие статусы
     * "Упущен телефонией", "Не дождался соединения с ОП", "Не принят оператором", "Вызов прекращен", "Не дозвонились
     * до КЦ", "Не дождался перевода на КЦ", "Просьба перезвонить"
     *
     * @param int  $leadId
     * @param bool $withFailed
     * @param $callStatusXmlId
     *
     * @return array
     */
    public function getHistoryByLead($leadId, $withFailed = false, $withResetAttempts = false, $callStatusXmlId = null)
    {
        $callStatusesList = new Callstatuseslist();
        $callResults = new Callresults();

        $historyResult = [];

        $callStatusesEntity = [];

        $leadId = (int) ($leadId ?? 0);

        // Refactored
        if(!empty($leadId)) {

            $callStatusesEntity = $callResults->getCallResultsList(
                ['*'],
                [
                    'UF_LEAD_ID' => $leadId,
                ],
                null,
                ['ID' => 'ASC'],
            );
        }

        if (empty($callStatusesEntity)) {
            return $historyResult;
        }

        //костыль последний звонок при вызове prepareLead может иметь еще не актуальный статус
        if(!empty($callStatusXmlId) && !empty($callStatusesEntity[count($callStatusesEntity) - 1]['UF_STATUS_CODE'])) {
            $callStatusesEntity[count($callStatusesEntity) - 1]['UF_STATUS_CODE'] = $callStatusXmlId;
        }

        $systemFailStatusValIds = $callStatusesList->getIgnoreStatusCode();

        if (!$withResetAttempts) {
            $systemFailStatusValIds = array_merge(
                $systemFailStatusValIds,
                $callStatusesList->getResetAttemptsStatusesCode()
            );
        }

        foreach ($callStatusesEntity as $callStatusItem) {
            if (!$withFailed) {
                if (in_array($callStatusItem['UF_STATUS_CODE'], $systemFailStatusValIds)) {
                    continue;
                }
            }

            $historyResult[$callStatusItem['ID']] = $callStatusItem;
        }

        return array_values($historyResult);
    }

    public function calcEffectiveIntervalCount($intervalData, $leadHistory)
    {
        $callIntervals = new Callintervals();

        $callStatusesList = new Callstatuseslist();

        $maxTotalCalls = $callIntervals->getMaxTotalCalls();

        $maxCallIntervalsCount = count($intervalData['EXPLODED']);

        $resetStatusesArr = $callStatusesList->getResetAttemptsStatusesCode();

        if (!empty($intervalData['UF_RESET_ATTEMPTS'])) {
            $resetAttemptsStatusesCount = 0;
            foreach ($leadHistory as $historyItem) {
                if (!empty($historyItem['UF_STATUS_CODE']) && in_array(
                        (int) ($historyItem['UF_STATUS_CODE']),
                        $resetStatusesArr
                    )) {
                    $resetAttemptsStatusesCount++;
                }
            }

            if ($resetAttemptsStatusesCount == 1) {
                $maxCallIntervalsCount *= 2;
            } elseif ($resetAttemptsStatusesCount >= 2) {
                $maxCallIntervalsCount *= $resetAttemptsStatusesCount;
            }
        }

        return $maxCallIntervalsCount < $maxTotalCalls ? $maxCallIntervalsCount : $maxTotalCalls;
    }

    /**
     * Проверка для блокировки дозвона если клиент бросил трубку от 2 раз и больше
     *
     * @param array $leadHistory
     *
     * @return bool
     */
    public function isBrokenCall($leadHistory) : bool
    {
        $isBrokenCall = false;
        if (!empty($leadHistory)) {
            $isBrokenCount = 0;
            foreach ($leadHistory as $historyItem) {
                if ($historyItem['UF_STATUS_CODE'] == '50000063673') {
                    $isBrokenCount++;
                }
            }

            if ($isBrokenCount >= 2) {
                $isBrokenCall = true;
            }
        }

        return $isBrokenCall;
    }

    /**
     * Онлайн операторы от типа (исходящий, входящий или предиктив) и кто на тренажере или нет
     *
     * @param      $callType
     * @param bool $callSimulatorIsEnabled
     *
     * @return array
     */
    public function getOnlineReadyEmployees($callType, $callSimulatorIsEnabled = false)
    {
        $voxProvider = new VoxProvider();

        $user = new User();

        $rsUsers = $user->getActiveCallCenterUsersMap();

        $callCenterEmployeesArr = $onlineEmployeesArr = [];

        $availableCallCenterStatus = $this->getAvailableCallStatus();

        foreach ($rsUsers as $userData) {
            $userTrainingIsEnabled = !empty($userData['UF_TRAINING_IS_ENABLED']);

            if (($userTrainingIsEnabled !== $callSimulatorIsEnabled) ||
                ($userData['UF_UIS_STATUS'] !== $availableCallCenterStatus['UF_UIS_ID']) ||
                !empty($userData['UF_UIS_CALL_SESSION']) || !empty($userData['UF_IS_POSTCALL'])
            ) {
                continue;
            }

            // В случае, если у оператора холд для входящих вызовов, проверяем актуальность этого холда
            if ($callType !== 'incoming') {
                if (($userData['UF_INCOMING_HOLD_TIME'] !== null) && (time() <= $userData['UF_INCOMING_HOLD_TIME'])) {
                    continue;
                }
            }

            $phoneIdFieldCode = match (InstanceHelper::getVatsProviderCode()) {
                VatProvider::VOX => 'UF_VOX_USER_NAME',
                default => 'UF_UIS_ID',
            };

            if (empty($userData[$phoneIdFieldCode])) {
                continue;
            }

            if ($this->isAllowedByUserPhoneMode($callType, $userData['UF_PHONE_MODE'])) {
                $callCenterEmployeesArr[] = [
                    'ID'               => $userData['ID'],
                    'UF_UIS_ID'        => $userData['UF_UIS_ID'],
                    'UF_VOX_USER_NAME' => $userData['UF_VOX_USER_NAME'],
                ];
            }
        }

        if (!empty($callCenterEmployeesArr)) {
            // Проверяем всех сотрудников КЦ на онлайн
            foreach ($callCenterEmployeesArr as $employeeItem) {

                if(!SocketService::checkUserOnline(intval($employeeItem['ID']))) {
                    continue;
                }

                $isReadyForCall = match (InstanceHelper::getVatsProviderCode()) {
                    VatProvider::VOX => (!empty($employeeItem['UF_VOX_USER_NAME']) && $voxProvider->userIsReadyForCall(
                            $employeeItem['UF_VOX_USER_NAME']
                        )),
                    default => (!empty($employeeItem['UF_UIS_ID']) && UisApiProvider::connected(
                            $employeeItem['UF_UIS_ID']
                        )),
                };

                if ($callSimulatorIsEnabled || $isReadyForCall) {
                    $onlineEmployeesArr[] = $employeeItem;
                }
            }
        }

        return $onlineEmployeesArr;
    }

    /**
     * Возращаем операторов на статусе доступен
     *
     * @return array
     */
    public function getAvailableCallStatus()
    {
        return $this->getCallCenterStatusByFilter(['UF_IS_AVAILABLE' => 1]);
    }

    /**
     * Проверка пользователя на возможность делать звонки (исходящий, входящий или предиктив)
     *
     * @param $callType
     * @param $userPhoneMode
     *
     * @return bool
     */
    public function isAllowedByUserPhoneMode($callType, $userPhoneMode = 'default')
    {
        $callIsAllowed = false;

        switch ($callType) {
            case 'outgoing':
                if ($userPhoneMode == 'default' || $userPhoneMode == 'outgoing-only') {
                    $callIsAllowed = true;
                }
            break;
            case 'incoming':
                if ($userPhoneMode == 'default' || $userPhoneMode == 'incoming-only') {
                    $callIsAllowed = true;
                }
            break;
            case 'predictive':
                if ($userPhoneMode == 'predictive') {
                    $callIsAllowed = true;
                }
            break;
        }

        return $callIsAllowed;
    }

    public function preparePotentialEmployeeForIncoming($orderId) : void
    {
        if (!InstanceHelper::isVoxVatsProvider()) {
            return;
        }

        $voxProvider = new VoxProvider();

        $user = new User();

        $rsUsers = $user->getActiveCallCenterUsersMap();

        // Получаем код статуса "Доступен"
        $availableCallCenterStatus = $this->getAvailableCallStatus();

        $potentialUsers = [];

        foreach ($rsUsers as $userData) {
            // Флаг включенного тренажера у пользователя
            $userTrainingIsEnabled = !empty($userData['UF_TRAINING_IS_ENABLED']);

            // Пропускаем пользователей, которые на тренажере или же в не доступном статусе
            if ($userTrainingIsEnabled || ($userData['UF_UIS_STATUS'] !== $availableCallCenterStatus['UF_UIS_ID'])) {
                continue;
            }

            $phoneIdFieldCode = match (InstanceHelper::getVatsProviderCode()) {
                VatProvider::VOX => 'UF_VOX_USER_NAME',
                default => 'UF_UIS_ID',
            };

            // Пропускаем пользователей, у которых нет настроек телефонии
            if (empty($userData[$phoneIdFieldCode])) {
                continue;
            }

            // Пропускаем пользователей у которых нет разрешения на прием входящих звонков
            if (!$this->isAllowedByUserPhoneMode('incoming', $userData['UF_PHONE_MODE'])) {
                continue;
            }

            // Проверяем, активный ли телефон у пользователя
            $isReadyForCall = match (InstanceHelper::getVatsProviderCode()) {
                VatProvider::VOX => (!empty($userData['UF_VOX_USER_NAME']) && $voxProvider->userIsReadyForCall(
                        $userData['UF_VOX_USER_NAME']
                    )),
                default => (!empty($userData['UF_UIS_ID']) && UisApiProvider::connected(
                        $userData['UF_UIS_ID']
                    )),
            };

            // Есть телелефон не активен, пропускаем
            if (!$isReadyForCall) {
                continue;
            }

            // Проверяем стабильность онлайна, пропускаем лишних
            if (!SocketService::checkUserOnline(intval($userData['ID']))) {
                continue;
            }

            // По первичным вводным юзер подходит, добавляем его в массив
            $potentialUsers[] = $userData;
        }

        // Если нет потенциальных операторов, то завершаем работу
        if (empty($potentialUsers)) {
            return;
        }

        // Дополнительно фильтруем потенциальных операторов по заказу
        $potentialUsers = $this->filterByOrderEmployees($potentialUsers, $orderId);

        if (empty($potentialUsers)) {
            return;
        }

        // Выбираем одного оператора
        shuffle($potentialUsers);
        $potentialOperatorId = $potentialUsers[0]['ID'];

        // Делаем этому оператору холд

        $user->updateUser(
            intval($potentialOperatorId),
            [
                'UF_INCOMING_HOLD_TIME' => time() + 15,
            ],
            true
        );
    }

    /**
     * Возращаем онлайн операторов прикрепленных к заказу
     *
     * @param $onlineReadyEmployees
     * @param $orderId
     *
     * @return array
     */
    protected function filterByOrderEmployees($onlineReadyEmployees, $orderId)
    {
        $orders = new Orders();

        $orderData = $orders->getOrderDataById($orderId, ['UF_CALL_CENTER_USERS', 'UF_CALL_CENTER_GROUPS']);

        $allowedEmployeesArr = [];

        if (!empty($orderData['CALL_CENTER_USERS']) || !empty($orderData['CALL_CENTER_GROUPS_USERS_IDS'])) {
            $callCenterUsersIds = [];

            $callCenterUsersIds = !empty($orderData['CALL_CENTER_USERS']) ? $orderData['CALL_CENTER_USERS'] : [];

            if (!empty($orderData['CALL_CENTER_GROUPS_USERS_IDS'])) {
                $callCenterUsersIds = array_merge($callCenterUsersIds, $orderData['CALL_CENTER_GROUPS_USERS_IDS']);
            }

            $callCenterUsersIds = array_unique($callCenterUsersIds);

            if (!empty($callCenterUsersIds)) {
                foreach ($onlineReadyEmployees as $employeeData) {
                    if (in_array($employeeData['ID'], $callCenterUsersIds)) {
                        $allowedEmployeesArr[] = $employeeData;
                    }
                }
            }
        }

        return $allowedEmployeesArr;
    }

    /**
     * Определяем сотрудника, которому отдадим вызов
     * Проверяем контекст участия в дозвоне
     * Если была просьба перезвонить за сотрудником даем приоритет
     *
     * @return array
     */
    protected function getNextEmployee($leadId, $readyEmployees)
    {
        if (count($readyEmployees) == 1) {
            return $readyEmployees[0];
        }

        $leadHistory = $this->getHistoryByLead($leadId, true);

        if (empty($leadHistory)) {
            return $readyEmployees[rand(0, count($readyEmployees) - 1)];
        }

        $employeesByPoint = $uisIdsByUserIds = $voxUserNameByUserIds = [];
        foreach ($readyEmployees as $readyEmployeeData) {
            $userId = $readyEmployeeData['ID'];
            $uisIdsByUserIds[$userId] = $readyEmployeeData['UF_UIS_ID'];
            $voxUserNameByUserIds[$userId] = $readyEmployeeData['UF_VOX_USER_NAME'];
            $employeesByPoint[$userId] = 0;
        }

        foreach ($leadHistory as $historyItem) {
            $userId = $historyItem['UF_USER_ID'];

            if (isset($employeesByPoint[$userId])) {
                // Проверяем контекст участия в дозвоне
                switch ($historyItem['UF_STATUS_CODE']) {
                    // Просьба перезвонить
                    case '50000063681':
                        $employeesByPoint[$userId] += 100;
                    break;
                    default:
                        $employeesByPoint[$userId] += 10;
                }

                if ($historyItem['UF_TALK_TIME_DURATION'] > 0) {
                    $floorTalkMinutes = floor($historyItem['UF_TALK_TIME_DURATION'] / 60);
                    if ($floorTalkMinutes > 0) {
                        $employeesByPoint[$userId] += $floorTalkMinutes * 100;
                    }
                }
            }
        }

        arsort($employeesByPoint);

        if (count($employeesByPoint) > 1) {
            $maxPoint = $employeesByPoint[array_key_first($employeesByPoint)];
            $similarEmployeesIds = [];
            foreach ($employeesByPoint as $employeeId => $employeePoint) {
                if ($employeePoint !== $maxPoint) {
                    continue;
                }

                $similarEmployeesIds[] = $employeeId;
            }

            $userId = $similarEmployeesIds[rand(0, count($similarEmployeesIds) - 1)];
        } else {
            $userId = array_key_first($employeesByPoint);
        }

        return [
            'ID'               => $userId,
            'UF_VOX_USER_NAME' => $voxUserNameByUserIds[$userId],
            'UF_UIS_ID'        => $uisIdsByUserIds[$userId],
        ];
    }

    /**
     * Изменяем информацию по оператору
     *
     * @param $userId
     * @param $params
     *
     * @return bool
     */
    public function updateCallCenterUserData($userId, $params)
    {
        $userId = intval($userId);

        if (empty($userId) || empty($params) || !is_array($params)) {
            return false;
        }

        $user = new User();
        $callCenterStatusesHistory = new Callcenterstatushistory();
        $callResults = new Callresults();

        $userData = $user->getUserForId($userId);

        $statusHasBeenChanged = false;
        $cDateTimeObj = new DateTime();

        $res = $user->updateUser($userId, $params, true);

        if (!empty($userData['UF_TRAINING_IS_ENABLED'])) {
            return $res;
        }

        //произошел новый звонок
        if (!empty($params['UF_UIS_CALL_SESSION'])) {
            // Создаем записи в истории о смене статусов
            $callCenterActiveCallStatus = $this->getActiveCallStatus();

            $callCenterStatusesHistory->createCallCenterStatusHistory(
                $userId,
                intval($callCenterActiveCallStatus['UF_UIS_ID']),
                false
            );

            $statusHasBeenChanged = true;

            // Проверим предыдущая сессия пользователя завершена
            // Refactored
            $callStatusRecordArr = $callResults->getCallResultsList(
                ['ID', 'UF_CLIENT_LEG_ID', 'UF_OPERATOR_LEG_ID', 'UF_ORDER_LEG_ID'],
                [
                    'UF_CALL_SESSION_ID' => $userData['UF_UIS_CALL_SESSION'],
                ],
                1,
            );

            //закрываем старый звонок
            if (!empty($callStatusRecordArr['UF_CLIENT_LEG_ID']) && !empty($callStatusRecordArr['UF_OPERATOR_LEG_ID']) && empty($callStatusRecordArr['UF_ORDER_LEG_ID'])) {
                switch (InstanceHelper::getVatsProviderCode()) {
                    case VatProvider::UIS:
                    case VatProvider::CG:
                        // Принудительно завершаем активные вызовы, в случае, если они зависли
                        UisApiProvider::finishCall($userData['UF_UIS_CALL_SESSION']);
                }
            }
        }

        if (isset($params['UF_IS_POSTCALL'])) {

            $newStatusId = $params['UF_UIS_STATUS'] ?? null;

            if (empty($newStatusId)) {
                $isManualSet = false;

                // Last User Status
                $lastManualStatus = $callCenterStatusesHistory->getList(
                    ['*'],
                    ['UF_EMPLOYEE' => $userId, 'UF_IS_MANUAL' => 1],
                    1,
                );

                if (!empty($lastManualStatus)) {
                    $newStatusId = (int) ($lastManualStatus['UF_STATUS_ID']);
                } else {
                    $availableCallStatus = $this->getAvailableCallStatus();
                    $newStatusId = $availableCallStatus['UF_UIS_ID'];
                }
            } else {
                $isManualSet = true;
            }

            $callCenterPostCallStatus = $this->getPostCallStatus();

            $callCenterStatusesHistory->createCallCenterStatusHistory(
                $userId,
                (!empty($params['UF_IS_POSTCALL'])) ? intval($callCenterPostCallStatus['UF_UIS_ID']) : intval(
                    $newStatusId
                ),
                $isManualSet
            );

            $statusHasBeenChanged = true;
        }

        if ($statusHasBeenChanged) {
            $user->updateUser($userId, ['UF_STATUS_LAST_UPDATE' => $cDateTimeObj->format('U')], true);
        }

        return $res;
    }

    /**
     * Возращаем операторов на статусе в звонке
     *
     * @return array
     */
    protected function getActiveCallStatus()
    {
        return $this->getCallCenterStatusByFilter(['UF_IS_ACTIVE_CALL' => 1]);
    }

    /**
     * Возращаем операторов на статусе в пост обработке
     *
     * @return array
     */
    protected function getPostCallStatus()
    {
        return $this->getCallCenterStatusByFilter(['UF_IS_POST_CALL' => 1]);
    }

    /**
     * Изменение статуса оператора по сокетам
     *
     * @param $userId
     *
     * @return true
     */
    public function sendEmployeeStatusBySocket($userId = null)
    {
        $user = new User();
        $userData = $user->getUserForId(intval($userId));
        $langIso = $userData['INTERFACE_LANGUAGE_CODE'];

        $statusTitlePropertyCode = strtoupper('UF_TITLE_' . $langIso);
        $statusData = $this->getEmployeeStatus($userData);

        SocketProvider::request(
            route: '/' . SocketEventRegistry::CHANGED_STATUS . '/',
            method: HTTPMethod::POST,
            body: [
                'channelId' => 'ch-' . $userData['ID'],
                'id'        => $statusData['UF_UIS_ID'],
                'name'      => $statusData[$statusTitlePropertyCode],
                'color'     => $statusData['UF_COLOR'],
                'mnemonic'  => 'deprecated',
                'caller'    => !empty($statusData['UF_IS_ACTIVE_CALL']) || !empty($statusData['UF_IS_POST_CALL']) || !empty($statusData['UF_IS_AVAILABLE']),
            ]
        );

        return true;
    }

    /**
     * Возращаем текущий статус пользователя
     *
     * @param $user
     *
     * @return array
     */
    public function getEmployeeStatus($user) : array
    {
        $statusData = [];

        // Проверяем, находится ли пользователь в постобработке

        $isActiveCall = $isPostCallBack = false;
        if (!empty($user)) {
            $isActiveCall = (!empty($user['UF_UIS_CALL_SESSION']));
            $isPostCallBack = (!empty($user['UF_IS_POSTCALL']));
            $employeeStatusId = (!empty($user['UF_UIS_STATUS'])) ? (int) ($user['UF_UIS_STATUS']) : '';
        }

        if ($isActiveCall) {
            $statusData = $this->getActiveCallStatus();
        } elseif ($isPostCallBack) {
            $statusData = $this->getPostCallStatus();
        } elseif (!empty($employeeStatusId)) {
            $statusData = $this->getCallCenterStatusByUisId($employeeStatusId);
        }

        if (empty($statusData)) {
            $statusTitlePropertyCode = 'UF_TITLE_' . strtoupper(Locale::current());

            $statusData = [
                'UF_UIS_ID'              => '',
                'UF_COLOR'               => '#dee2e6',
                $statusTitlePropertyCode => Liner::t('Unknown'),
            ];
        }

        return $statusData;
    }

    /**
     * Возращаем оператора по id в uis
     *
     * @param $ufUisId
     *
     * @return array
     * @todo перенести uisapi
     */
    protected function getCallCenterStatusByUisId($ufUisId)
    {
        return $this->getCallCenterStatusByFilter(['UF_UIS_ID' => $ufUisId]);
    }

    /**
     * Не удалось выполнить переадресацию входящего вызова на сотрудника
     * Находим запись в истории звонков, связанную с этой сессией
     * Находим лид
     * В любом случае, даем команду на воспроизведение голосового сообщения пользователю
     * Планируем дозвон по лиду
     * Если звонок висит на операторе меняем есу статус и выводи сообщение
     *
     * @api
     */
    protected function internalFailCall()
    {
        $user = new User();

        $callResults = new Callresults();

        // Не удалось выполнить переадресацию входящего вызова на сотрудника

        $inputDataRaw = file_get_contents("php://input");

        if (empty($inputDataRaw)) {
            $this->returnVatsResult(
                [
                    'returned_code' => 0, // Недостаточно информации для обработки
                ]
            );
        }

        $leads = new Leads();

        $inputDataArr = json_decode($inputDataRaw, 1);

        $callSessionId = $inputDataArr['call_session_id'];

        if (!empty($callSessionId)) {
            // Находим запись в истории звонков, связанную с этой сессией
            // Refactored
            $callStatusRecordArr = $callResults->getCallResultsList(
                ['*'],
                [
                    'UF_CALL_SESSION_ID' => $callSessionId,
                ],
                1,
            );

            if (!empty($callStatusRecordArr)) {
                // Запись найдена, ок, теперь ищем лид, по этой записи
                // Refactored
                $leadArr = $leads->getLeadList(
                    [
                        'ID',
                        'UF_ORDER',
                    ],
                    [
                        'ID'        => $callStatusRecordArr['UF_LEAD_ID'],
                        'UF_STATUS' => 'primary',
                    ],
                    1
                );

                if (!empty($leadArr)) {
                    // Лид найден, ок - обрабатываем его должным образом

                    // Сначала сотрем инфу активного вызова

                    $leads->updateLeadProperty(
                        $leadArr['ID'],
                        [
                            'UF_UIS_CALL_ID'     => '',
                            'UF_LOCAL_CALL_ID'   => '',
                            'UF_UIS_CALL_START_TIME' => '',
                        ],
                        'UIS_INTERNAL_FAIL_CALL'
                    );

                    // Теперь запланируем дозвон по лиду
                    $this->prepareLead(
                        $leadArr['ID'],
                        (int) ($leadArr['UF_ORDER']),
                        'Автоматическая обработка лида',
                        88888888888
                    );

                    // Осталось разобраться с оператором
                    if (!empty($callStatusRecordArr['UF_USER_ID'])) {
                        $userData = $user->getUserForId(intval($callStatusRecordArr['UF_USER_ID']));

                        $currentUserCallSessionId = $userData['UF_UIS_CALL_SESSION'];
                        if ($currentUserCallSessionId == $callStatusRecordArr['UF_CALL_SESSION_ID']) {
                            // Отправляем уведомление на фронт о том, что звонок автоматически обработан
                            $this->sendFrontAutoPrepareNotify($userData['ID'], $leadArr['ID']);

                            // Убираем у оператора признак пост-обработки и ID разговора
                            $this->updateCallCenterUserData(
                                $userData['ID'],
                                [
                                    'UF_IS_POSTCALL'      => '',
                                    'UF_UIS_CALL_SESSION' => '',
                                ]
                            );

                            // Отправляем оператору его новый статус
                            $this->sendEmployeeStatusBySocket($userData['ID']);
                        }
                    }
                }
            }
        }

        // В любом случае, даем команду на воспроизведение голосового сообщения пользователю
        $this->returnVatsResult(
            [
                'returned_code' => 1, // Воспроизвести сообщение пользователю из сценария
            ]
        );
    }

    /**
     * Отправляем уведомление на фронт об автоматической обработке Лида
     *
     * @param $userId
     * @param $leadId
     *
     * @return void
     */
    public function sendFrontAutoPrepareNotify($userId, $leadId): void
    {
        // Отправляем уведомление на фронт об автоматической обработке Лида
        SocketProvider::request(
            route: '/' . SocketEventRegistry::AUTO_PREPARE_CALL . '/',
            method: HTTPMethod::POST,
            body: [
                'channelId' => 'ch-' . $userId,
                'leadId'    => $leadId,
            ]
        );
    }

    /**
     * Отправляем уведомление на фронт о том, что AI еще разговаривает с клиентом
     *
     * @param $userId
     * @param $leadId
     *
     * @return void
     */
    public function sendFrontAiIsTalkingNotify($userId, $leadId): void
    {
        // Отправляем уведомление на фронт об автоматической обработке Лида
        SocketProvider::request(
            route: '/' . SocketEventRegistry::AI_IS_TALKING . '/',
            method: HTTPMethod::POST,
            body: [
                'channelId' => 'ch-' . $userId,
                'leadId'    => $leadId,
            ]
        );
    }

    /**
     * Отправляем уведомление на фронт о том, что AI еще разговаривает с клиентом
     *
     * @param $userId
     * @param $leadId
     *
     * @return void
     */
    public function sendFrontAiIsFinishedNotify($userId, $leadId): void
    {
        // Отправляем уведомление на фронт об автоматической обработке Лида
        SocketProvider::request(
            route: '/' . SocketEventRegistry::AI_IS_FINISHED . '/',
            method: HTTPMethod::POST,
            body: [
                'channelId' => 'ch-' . $userId,
                'leadId'    => $leadId,
            ]
        );
    }

    //
    // Planning internal methods

    /**
     *  Не удалось выполнить переадресацию предиктивного вызова на сотрудника
     * Находим запись в истории звонков, связанную с этой сессией
     * Находим лид
     * В любом случае, даем команду на воспроизведение голосового сообщения пользователю
     * Планируем дозвон по лиду
     * Если звонок висит на операторе меняем есу статус и выводи сообщение
     *
     * @api
     */
    protected function predictiveFailCall()
    {
        $leads = new Leads();

        $user = new User();

        $callResults = new Callresults();

        // Не удалось выполнить переадресацию предиктивного вызова на сотрудника

        $inputDataRaw = file_get_contents("php://input");

        if (empty($inputDataRaw)) {
            $this->returnVatsResult(
                [
                    'returned_code' => 0, // Недостаточно информации для обработки
                ]
            );
        }

        $inputDataArr = json_decode($inputDataRaw, 1);

        $callSessionId = $inputDataArr['call_session_id'];

        if (!empty($callSessionId)) {
            // Находим запись в истории звонков, связанную с этой сессией
            // Refactored
            $callStatusRecordArr = $callResults->getCallResultsList(
                ['*'],
                [
                    'UF_CALL_SESSION_ID' => $callSessionId,
                ],
                1
            );

            if (!empty($callStatusRecordArr)) {
                // Запись найдена, ок, теперь ищем лид, по этой записи
                // Refactored
                $leadArr = $leads->getLeadList(
                    [
                        'ID',
                        'UF_ORDER',
                    ],
                    [
                        'ID'        => $callStatusRecordArr['UF_LEAD_ID'],
                        'UF_STATUS' => 'primary',
                    ],
                    1
                );

                if (!empty($leadArr)) {
                    // Лид найден, ок - обрабатываем его должным образом

                    // Сначала сотрем инфу активного вызова

                    $leads->updateLeadProperty(
                        $leadArr['ID'],
                        [
                            'UF_UIS_CALL_ID'         => '',
                            'UF_LOCAL_CALL_ID'       => '',
                            'UF_UIS_CALL_START_TIME' => '',
                        ],
                        'UIS_PREDICTIVE_FAIL_CALL'
                    );

                    // Теперь запланируем дозвон по лиду
                    $this->prepareLead(
                        $leadArr['ID'],
                        (int) ($leadArr['UF_ORDER']),
                        'Автоматическая обработка лида',
                        88888888888
                    );

                    // Осталось разобраться с оператором
                    if (!empty($callStatusRecordArr['UF_USER_ID'])) {
                        $userData = $user->getUserForId(intval($callStatusRecordArr['UF_USER_ID']));

                        $currentUserCallSessionId = $userData['UF_UIS_CALL_SESSION'];
                        if ($currentUserCallSessionId == $callStatusRecordArr['UF_CALL_SESSION_ID']) {
                            // Отправляем уведомление на фронт о том, что звонок автоматически обработан
                            $this->sendFrontAutoPrepareNotify($userData['ID'], $leadArr['ID']);

                            // Убираем у оператора признак пост-обработки и ID разговора
                            $this->updateCallCenterUserData(
                                $userData['ID'],
                                [
                                    'UF_IS_POSTCALL'      => '',
                                    'UF_UIS_CALL_SESSION' => '',
                                ]
                            );

                            // Отправляем оператору его новый статус
                            $this->sendEmployeeStatusBySocket($userData['ID']);
                        }
                    }
                }
            }
        }

        // В любом случае, даем команду на воспроизведение голосового сообщения пользователю
        $this->returnVatsResult(
            [
                'returned_code' => 1, // Воспроизвести сообщение пользователю из сценария
            ]
        );
    }

    /**
     * Used by VoxImplant only.
     * @return void|null
     */
    protected function predictiveAiEvents()
    {
        if (!InstanceHelper::isVoxVatsProvider()) {
            return IO::jsonDeadResponse(Liner::t('Not allowed Vats provider'));
        }

        $input = file_get_contents("php://input");
        if (empty($input)) {
            return IO::jsonDeadResponse(Liner::t('Request body not passed'));
        }

        $data = json_decode($input, 1);

        $voxProvider = new VoxProvider();
        $aiEventData = $voxProvider->exportAiEventData($data);

        if (empty($aiEventData['callSessionId']) || empty($aiEventData['eventCode'])) {
            return IO::jsonDeadResponse(Liner::t('Insufficient data to process'));
        }

        $callResults = new Callresults();
        $currentCallItem = $callResults->getCallResultsList(
            ['*'],
            [
                'UF_CALL_SESSION_ID' => $aiEventData['callSessionId'],
            ],
            1
        );

        if (empty($currentCallItem)) {
            return IO::jsonDeadResponse(Liner::t('Failed to identify the call'));
        }

        // Достаем данные оператора
        $user = new User();
        $userData = $user->getUserForId(intval($currentCallItem['UF_USER_ID']));
        if (empty($userData)) {
            return IO::jsonDeadResponse(Liner::t('Failed to get employee information'));
        }

        $currentUserCallSessionId = $userData['UF_UIS_CALL_SESSION'] ?? 0;

        $isCurrentUserCall = ($currentUserCallSessionId == $aiEventData['callSessionId']);

        if ($isCurrentUserCall) {

            switch ($aiEventData['eventCode']) {
                case 'ai_is_talking':
                    $this->sendFrontAiIsTalkingNotify($userData['ID'], $currentCallItem['UF_LEAD_ID']);
                    break;
                case 'ai_is_finished':
                    $this->sendFrontAiIsFinishedNotify($userData['ID'], $currentCallItem['UF_LEAD_ID']);
                    break;
                default:
            }

        }

        return IO::jsonDeadResponse(Liner::t('Event handled successfully'), true);
    }

    /**
     * @throws SocketException
     */
    protected function legIsConnected()
    {
        $input = file_get_contents("php://input");
        if (empty($input)) {
            return IO::jsonDeadResponse(Liner::t('Request body not passed'));
        }

        $data = json_decode($input, 1);

        $callResults = new Callresults();

        // Подготавливаем данные из уведомления
        switch (InstanceHelper::getVatsProviderCode()) {
            case VatProvider::VOX:
                $voxProvider = new VoxProvider();
                $legIsConnectedData = $voxProvider->exportLegIsConnectedData($data);
            break;
            case VatProvider::UIS:
            case VatProvider::CG:
            default:
                $legIsConnectedData = UisApiProvider::exportLegIsConnectedData($data);
        }

        if (empty($legIsConnectedData['callSessionId']) || empty($legIsConnectedData['legId'])) {
            return IO::jsonDeadResponse(Liner::t('Insufficient data to process'));
        }

        // Refactored
        $currentCallItem = $callResults->getCallResultsList(
            ['*'],
            [
                'UF_CALL_SESSION_ID' => $legIsConnectedData['callSessionId'],
            ],
            1
        );

        if (empty($currentCallItem)) {
            return IO::jsonDeadResponse(Liner::t('Failed to identify the call'));
        }

        $updatedFieldName = $legType = '';
        $orderEmployeeId = 0;
        if ($legIsConnectedData['isAi']) {
            $updatedFieldName = 'UF_AI_LEG_ID';
            $legType = VatLeg::AI;
        } elseif ($legIsConnectedData['isOperator']) {
            $updatedFieldName = 'UF_OPERATOR_LEG_ID';
            $legType = VatLeg::AGENT;
        } elseif (empty($currentCallItem['UF_CLIENT_LEG_ID']) && empty($currentCallItem['UF_ORDER_LEG_ID'])) {
            $updatedFieldName = 'UF_CLIENT_LEG_ID';
            $legType = VatLeg::CLIENT;
        } elseif (!empty($currentCallItem['UF_CLIENT_LEG_ID']) && !empty($currentCallItem['UF_OPERATOR_LEG_ID']) && empty($currentCallItem['UF_ORDER_LEG_ID'])) {
            $updatedFieldName = 'UF_ORDER_LEG_ID';
            $orderEmployeeId = $legIsConnectedData['employeeId'];
            $legType = VatLeg::TRANSFER;
        }

        if (empty($updatedFieldName) || empty($legType)) {
            IO::jsonDeadResponse(Liner::t('Could not identify shoulder'));
        }

        $updateFields = [
            $updatedFieldName      => $legIsConnectedData['legId'],
            'UF_ORDER_EMPLOYEE_ID' => $orderEmployeeId,
            'UF_LAST_EDITOR'       => 0,
        ];

        // Changing call status from "Not accepted by Agent" to "Post. processing is not completed"
        if ($legIsConnectedData['isOperator'] && $currentCallItem['UF_STATUS_CODE'] == 88888888888) {
            $updateFields['UF_STATUS_CODE'] = 66666666666; // Post. processing is not completed
        }

        $callStatusesHlEntityUpdResult = $callResults->updateCallResult(
            intval($currentCallItem['ID']),
            $updateFields
        );

        if ($currentCallItem['UF_LEAD_ID']) {
            SocketService::sendLeadUpdateEvent(
                leadId: $currentCallItem['UF_LEAD_ID'],
                eventCode: SocketEventRegistry::CALL_CONNECTED,
                eventData: [
                    'legId' => $legIsConnectedData['legId'],
                    'legType' => $legType,
                    'callSessionId' => $currentCallItem['UF_CALL_SESSION_ID']
                ]
            );
        }

        return IO::jsonDeadResponse('', !empty($callStatusesHlEntityUpdResult));
    }

    /**
     * Обрыв звонка
     * По id сессии звонка пытаемся определить лид и оператора
     * Отправляем уведомление о завершении разговора оператору на фронт
     * Убедимся в том, что оператор смог принять этот звонок
     * Так же уведомляем оператора если "Бросил трубку клиент" или "Бросил трубку оператора заказа"
     * Проставляем признак пост-обработки оператору
     *
     * @throws SocketException
     * @api
     */
    protected function legIsDisconnected()
    {

        $input = file_get_contents("php://input");
        if (empty($input)) {
            return IO::jsonDeadResponse(Liner::t('Request body not passed'));
        }

        $user = new User();
        $callResults = new Callresults();

        $data = json_decode($input, 1);

        switch (InstanceHelper::getVatsProviderCode()) {
            case VatProvider::VOX:
                $voxProvider = new VoxProvider();
                $legIsDisconnectedData = $voxProvider->exportLegIsDisconnectedData($data);
            break;
            case VatProvider::UIS:
            case VatProvider::CG:
            default:
                $legIsDisconnectedData = UisApiProvider::exportLegIsDisconnectedData($data);
        }

        if (empty($legIsDisconnectedData['callSessionId']) || empty($legIsDisconnectedData['legId'])) {
            return IO::jsonDeadResponse(Liner::t('Insufficient data to process'));
        }

        // Refactored
        $currentCallItem = $callResults->getCallResultsList(
            ['*'],
            [
                'UF_CALL_SESSION_ID' => $legIsDisconnectedData['callSessionId'],
            ],
            1
        );

        if (empty($currentCallItem)) {
            return IO::jsonDeadResponse(Liner::t('Failed to identify the call'));
        }

        if (empty($legIsDisconnectedData['leadId'])) {
            $legIsDisconnectedData['leadId'] = $currentCallItem['UF_LEAD_ID'];
        }

        if (empty($legIsDisconnectedData['leadId'])) {
            return IO::jsonDeadResponse(Liner::t('Failed to identify Lead'));
        }

        // Корректируем Лид
        $legIsDisconnectedData['leadId'] = $this->correctLeadId($legIsDisconnectedData['leadId']);

        // Достаем данные оператора
        $userData = [];
        $isCurrentUserCall = false;

        $userId = (isset($currentCallItem['UF_USER_ID'])) ? intval($currentCallItem['UF_USER_ID']) : 0;
        if ($userId) {
            $userData = $user->getUserForId($userId);
            if ($userData) {
                $currentUserCallSessionId = $userData['UF_UIS_CALL_SESSION'] ?? 0;
                $isCurrentUserCall = ($currentUserCallSessionId == $legIsDisconnectedData['callSessionId']);
            }
        }

        $updatedFieldName = $legType = '';

        if ($legIsDisconnectedData['isOperator']) {
            $updatedFieldName = 'UF_OPERATOR_LEG_ID';
            $legType = VatLeg::AGENT;

            if ($isCurrentUserCall) {
                // Отправляем уведомление о завершении разговора оператору на фронт
                //                $this->sendFrontFinishNotify($userId, $leadId);

                // Убедимся в том, что оператор смог принять этот звонок
                if (($legIsDisconnectedData['isFailed'] && (($legIsDisconnectedData['finishReason'] == 'timeout') || ($legIsDisconnectedData['finishReason'] == 'subscriber_disconnects'))) || (!$legIsDisconnectedData['isFailed'] && ($legIsDisconnectedData['finishReason'] == 'operator_disconnects') && (empty($currentCallItem['UF_CLIENT_LEG_ID'])) && (empty($currentCallItem['UF_ORDER_LEG_ID'])) && empty($legIsDisconnectedData['talkTimeDuration']) && $legIsDisconnectedData['waitTimeDuration'] >= 30) || (empty($legIsDisconnectedData['isFailed']) && empty($currentCallItem['UF_ORDER_LEG_ID']) && !empty($legIsDisconnectedData['voiceMailIsDetected'])) || (   // Predictive bug fix
                        ($legIsDisconnectedData['callSource'] == 'callapi_scenario_call') && ($legIsDisconnectedData['direction'] == 'out') && ($legIsDisconnectedData['finishReason'] == 'operator_disconnects') && (empty($legIsDisconnectedData['talkTimeDuration'])) && ($legIsDisconnectedData['waitTimeDuration'] == $legIsDisconnectedData['totalTimeDuration']))) {
                    // Убираем признак пост-обработки у оператора
                    $this->updateCallCenterUserData(
                        $userData['ID'],
                        [
                            'UF_IS_POSTCALL' => '',
                        ]
                    );

                    $this->sendFrontAutoPrepareNotify($userData['ID'], $legIsDisconnectedData['leadId']);
                } else {
                    /*
                     * Проставляем признак пост-обработки оператору, если он в статусе "Доступен"
                     * и нет информации о завершенной пост обработке
                     */
                    $statusesMap = $this->getEmployeeStatusesMap(true);
                    if (($statusesMap[$userData['UF_UIS_STATUS']] == 'available') && empty(($currentCallItem['UF_USER_UPDATE_DATE']))) {
                        $this->updateCallCenterUserData(
                            $userData['ID'],
                            [
                                'UF_IS_POSTCALL' => 1,
                            ]
                        );
                    }
                }

                // Убираем идентификатор звонка из пользовательского поля оператора
                $this->updateCallCenterUserData(
                    $userData['ID'],
                    [
                        'UF_UIS_CALL_SESSION' => '',
                    ]
                );

                // Отправляем статус оператору на фронт
                $this->sendEmployeeStatusBySocket($userData['ID']);

                $this->rabbitDialer();
            }

        } elseif (!empty($currentCallItem['UF_CLIENT_LEG_ID']) && $currentCallItem['UF_CLIENT_LEG_ID'] == $legIsDisconnectedData['legId']) {
            // Бросил трубку клиент
            $updatedFieldName = 'UF_CLIENT_LEG_ID';
            $legType = VatLeg::CLIENT;

            if ($isCurrentUserCall) {
                $this->sendClientClosedNotify($userData['ID'], $legIsDisconnectedData['leadId'], 'client');
            }
        } elseif (!empty($currentCallItem['UF_ORDER_LEG_ID']) && $currentCallItem['UF_ORDER_LEG_ID'] == $legIsDisconnectedData['legId']) {
            // Бросил трубку оператора заказа
            $updatedFieldName = 'UF_ORDER_LEG_ID';
            $legType = VatLeg::TRANSFER;

            if ($isCurrentUserCall) {
                $this->sendClientClosedNotify($userData['ID'], $legIsDisconnectedData['leadId'], 'sd');
            }
        } elseif ($legIsDisconnectedData['isAi']){
            $updatedFieldName = 'UF_AI_LEG_ID';
            $legType = VatLeg::AI;
        }

        if (!empty($updatedFieldName)) {
            $callResults->updateCallResult(
                intval($currentCallItem['ID']),
                [
                    $updatedFieldName => '',
                    'UF_LAST_EDITOR'  => 0,
                ]
            );
        }

        SocketService::sendLeadUpdateEvent(
            leadId: $currentCallItem['UF_LEAD_ID'],
            eventCode: SocketEventRegistry::CALL_DISCONNECTED,
            eventData: [
                'legId' => $legIsDisconnectedData['leadId'],
                'legType' => $legType,
                'callSessionId' => $currentCallItem['UF_CALL_SESSION_ID']
            ]
        );

        return IO::jsonDeadResponse(Liner::t('Event handled successfully'), true);
    }

    protected function correctLeadId($sourceLeadId)
    {
        $sourceLeadId = intval($sourceLeadId);

        if (empty($sourceLeadId)) {
            return false;
        }

        $correctedLeadId = $sourceLeadId;

        $leads = new Leads();

        // Refactored
        $sourceLeadData = $leads->getLeadList(
            [
                'ID',
            ],
            [
                'ID'        => $sourceLeadId,
                'UF_STATUS' => 'fail-straight',
            ],
            1,
        );

        if (!empty($sourceLeadData)) {
            // Refactored
            $correctedLeadData = $leads->getLeadList(
                [
                    'ID',
                ],
                [
                    'UF_PREVIOUS_LEAD' => $sourceLeadData['ID'],
                    'UF_LEAD_TYPE'     => 'selection',
                ],
                1,
            );

            if (!empty($correctedLeadData)) {
                $correctedLeadId = $correctedLeadData['ID'];
            }
        }

        return $correctedLeadId;
    }

    /**
     * Запуск rabbit для инициализации звонка
     *
     * @return true
     * @throws \Throwable
     */
    public function rabbitDialer($dialCount = 1)
    {
        for ($i = 0; $i < $dialCount; $i++) {
            RabbitProvider::send(RabbitQueue::DIALER, ['is_silent_gold' => true]);
        }

        return true;
    }

    /**
     * Отправляем уведомление на фронт об автоматической обработке Лида по сокетам
     *
     * @param $userId
     * @param $leadId
     * $param $text
     * @param $text
     * @return void
     */
    private function sendClientClosedNotify($userId, $leadId, $text): void
    {
        // Отправляем уведомление на фронт об автоматической обработке Лида
        SocketProvider::request(
            route: '/' . SocketEventRegistry::LEG_IS_DISCONNECTED . '/',
            method: HTTPMethod::POST,
            body: [
                'channelId' => 'ch-' . $userId,
                'leadId'    => $leadId,
                'text'      => $text,
            ]
        );
    }

    /**
     * @throws \Throwable
     */
    protected function finishCallHook()
    {
        $leads = new Leads();
        $voxProvider = new VoxProvider();
        $user = new User();
        $callResults = new Callresults();

        $callCenterUserData = [];

        $input = file_get_contents("php://input");

        if (empty($input)) {
            return IO::jsonDeadResponse(Liner::t('Request body not passed'));
        }

        $data = json_decode($input, 1);

        // Подготавливаем данные из уведомления
        $finishCallData = match (InstanceHelper::getVatsProviderCode()) {
            VatProvider::VOX => $voxProvider->exportCallFinishData($data),
            default => UisApiProvider::exportCallFinishData($data),
        };

        if (empty($finishCallData['callSessionId'])) {
            return IO::jsonDeadResponse(Liner::t('Call session identifier not passed'));
        }

        /*
         * Пытаемся поправить мгновенное завершение звонка
         * есть подозрение, что в данной ситуации уведомление приходит слишком быстро
         */

        if ((($finishCallData['direction'] == 'in') && empty($finishCallData['employeeId'])) || (($finishCallData['direction'] == 'out') && ($finishCallData['callSource'] == 'callapi_scenario_call'))) {
            sleep(5);
        }

        // Достаем сущность для работы со статусами
        $callStatusEntityArr = $this->getCallStatusEntity($finishCallData['callSessionId']);

        if (empty($callStatusEntityArr)) {
            return IO::jsonDeadResponse(Liner::t('Failed to get call information'));
        }

        //
        // Если ID Лида не поступил, то стоит проверить, возможно это был входящий звонок
        if (empty($finishCallData['leadId']) && !empty($callStatusEntityArr['UF_LEAD_ID'])) {
            $finishCallData['leadId'] = $callStatusEntityArr['UF_LEAD_ID'];
        }

        // Если ID Лида удалось вычислить, то стираем ID разговора и время начала разговора
        if (!empty($finishCallData['leadId'])) {
            $oldLeadId = $finishCallData['leadId'];

            // Предварительно корректируем ID Лида (реал-тайм подбор)
            $finishCallData['leadId'] = $this->correctLeadId($finishCallData['leadId']);

            //поднимаем последний session по лиду он должен совпадать с $callSessionId

            $getLastCallSessionId = $this->getLastCallSessionId(intval($finishCallData['leadId']));

            //это также связано с (реал-тайм подбор) пока оператор не закроет звонок будет старый лид
            if (empty($getLastCallSessionId)) {
                $getLastCallSessionId = $this->getLastCallSessionId(intval($oldLeadId));
            }

            // CallGear and UIS trouble
            // TODO: We should to check notification time instead current VATS Provider
            // notification time should be nearest from current time()
            // $finishCallData['callSessionId'] !== $getLastCallSessionId + new check
            // But before update this block, we should be sure, UIS and CallGear sending correct notification time
            if (!InstanceHelper::isVoxVatsProvider() &&
                ($finishCallData['callSessionId'] !== $getLastCallSessionId)
            ) {
                LogService::warning(['finishCallData' => $finishCallData], ['vats', 'finishCallHook', 'uis_call_gear_error']);
                return IO::jsonDeadResponse('ok', true);
            }

            $leadsProps = [
                'UF_UIS_CALL_ID'         => '',
                'UF_UIS_CALL_START_TIME' => '',
                'UF_LOCAL_CALL_ID'       => '',
            ];

            $this->getLeadsController()->updateLeadProperty(
                $finishCallData['leadId'],
                $leadsProps,
                'UIS_FINISH_CALL_HOOK'
            );
        }

        $isPredictiveCall = !empty($callStatusEntityArr['UF_IS_PREDICTIVE']);

        $callCenterUserId = intval($callStatusEntityArr['UF_USER_ID']);
        if (!$isPredictiveCall && $callStatusEntityArr['UF_DIRECTION'] != 2 && empty($callCenterUserId)) {
            return IO::jsonDeadResponse(Liner::t('Failed to identify employee'));
        }

        if (!empty($callCenterUserId)) {
            $callCenterUserData = $user->getUserForId($callCenterUserId);

            if (empty($callCenterUserData)) {
                return IO::jsonDeadResponse(Liner::t('Failed to get employee information'));
            }

            // Если ID сотрудника в уведомлении от UIS пустой, значит вызов завершился до назначения сотрудника. Не проблема
            if (empty($finishCallData['employeeId'])) {
                switch (InstanceHelper::getVatsProviderCode()) {
                    case VatProvider::VOX:
                        $finishCallData['employeeId'] = $callCenterUserData['UF_VOX_USER_NAME'];
                    break;
                    case VatProvider::UIS:
                    case VatProvider::CG:
                    default:
                        if (!empty($callCenterUserData['UF_UIS_ID'])) {
                            $finishCallData['employeeId'] = (int) ($callCenterUserData['UF_UIS_ID']);
                        }
                }
            }
        }

        // Продолжать стоит, только если есть явные признаки годного звонка
        if (!empty($finishCallData['leadId'])) {

            $isCurrentUserCall = false;
            $currentUserCallSessionId = null;

            if (!empty($callCenterUserData)) {
                $currentUserCallSessionId = intval($callCenterUserData['UF_UIS_CALL_SESSION']);
                $isCurrentUserCall = ($currentUserCallSessionId == $finishCallData['callSessionId']);
            }

            // Готовим массив для обновления записи со статусом разговора
            $newCallStatusData = [
                'UF_LEAD_ID'             => $finishCallData['leadId'],
                'UF_LAST_EDITOR'         => 0,
                'UF_TOTAL_TIME_DURATION' => $finishCallData['totalTimeDuration'],
                'UF_WAIT_TIME_DURATION'  => $finishCallData['waitTimeDuration'],
                'UF_TALK_TIME_DURATION'  => $finishCallData['talkTimeDuration'],
            ];

            // Достаем информацию о лиде
            // Refactored
            $leadRes = $leads->getLeadList(
                [
                    'ID',
                    'UF_ORDER',
                ],
                [
                    'ID' => $finishCallData['leadId'],
                ],
                1,
            );

            $orderId = (!empty($leadRes['UF_ORDER'])) ? (int) ($leadRes['UF_ORDER']) : null;

            if (empty($orderId)) {
                return IO::jsonDeadResponse(Liner::t('Failed to get lead order information'));
            }

            // Автоматически обрабатываем вызовы, в которых оператор или абонент не взяли трубку
            if (!empty($finishCallData['employeeId']) &&
                !empty($finishCallData['isLost']) &&
                (
                    ($finishCallData['finishReason'] == 'timeout') ||
                    ($finishCallData['finishReason'] == 'subscriber_disconnects') ||
                    ($finishCallData['finishReason'] == 'no_success_subscriber_call') ||
                    ($finishCallData['finishReason'] == 'operator_channels_busy')
                ) && ($finishCallData['totalTimeDuration'] == $finishCallData['waitTimeDuration'])
                && empty($finishCallData['lastTalkedEmployeeId']))
            {
                switch ($finishCallData['finishReason']) {
                    case 'timeout':
                        $callStatusXmlId = '88888888888'; // "Не принят оператором"
                    break;
                    case 'operator_channels_busy':
                        if ($isPredictiveCall) {
                            $callStatusXmlId = '88888888888'; // "Не принят оператором"
                            $newCallStatusData['UF_USER_ID'] = 0;
                        } else {
                            //                        }elseif($finishCallData['direction'] == 'in' ){
                            $callStatusXmlId = '88888888888'; // "Не принят оператором"
                        }
                    break;
                    case 'subscriber_disconnects':
                    case 'no_success_subscriber_call':
                        $callStatusXmlId = '50000063670'; // Не дозвонились до клиента

                        if (!empty($finishCallData['voiceMailIsDetected'])) {
                            $callStatusXmlId = '33333333333';
                        }

                    break;
                    default:
                }

                $newCallStatusData['UF_STATUS_CODE'] = $callStatusXmlId;
                $this->prepareLead(
                    $finishCallData['leadId'],
                    $orderId,
                    Liner::t('Automatic lead processing'),
                    $callStatusXmlId
                );

                // Если оператор не принял звонок, то проверяем сколько звонков подряд он уже упустил
                // если звонков 3 или больше, то принудительно убираем его с линии
                if ($callStatusXmlId == '88888888888') {
                    $this->checkOperatorForPassOutgoing();
                }

                // Фикс проблемы с очень быстрым сбросом звонка клиентом, в момент делегации вызова на оператора
                $availableCallCenterStatus = $this->getAvailableCallStatus();
                if ($isPredictiveCall &&
                    $isCurrentUserCall &&
                    empty($callCenterUserData['UF_IS_POSTCALL']) &&
                    ($callCenterUserData['UF_UIS_STATUS'] == $availableCallCenterStatus['UF_UIS_ID'])
                ) {
                    $this->updateCallCenterUserData(
                        $callCenterUserData['ID'],
                        [
                            'UF_IS_POSTCALL'      => '',
                            'UF_UIS_CALL_SESSION' => '',
                        ]
                    );
                    $this->sendEmployeeStatusBySocket($callCenterUserData['ID']);
                    $this->sendFrontAutoPrepareNotify($callCenterUserData['ID'], $finishCallData['leadId']);
                }


            } elseif (($finishCallData['direction'] == 'out') && (!empty($finishCallData['isLost']) || !empty($finishCallData['voiceMailIsDetected']))) {
                // Выполняем проверку, можно ли обработать данный лид автоматически, без оператора
                if (!$finishCallData['isTransfer'] && (($finishCallData['finishReason'] == 'no_success_subscriber_call') || ($finishCallData['finishReason'] == 'operator_disconnects')) && ((empty($finishCallData['lastTalkedEmployeeId']) && empty($finishCallData['talkTimeDuration']) && ($finishCallData['waitTimeDuration'] >= 30)) || $finishCallData['voiceMailIsDetected']) && empty($callStatusEntityArr['UF_LAST_EDITOR']) && !$isPredictiveCall) {
                    // Обрабатываем Лид автоматически, если оператор не успел его обработать
                    $callStatusXmlId = '50000063670'; // Статус "Не дозвонились до клиента"
                    if (!empty($finishCallData['voiceMailIsDetected'])) {
                        $callStatusXmlId = '33333333333';
                    }

                    $newCallStatusData['UF_STATUS_CODE'] = $callStatusXmlId;
                    $this->prepareLead(
                        $finishCallData['leadId'],
                        $orderId,
                        Liner::t('Automatic lead processing'),
                        $callStatusXmlId
                    );

                    if (!empty($isCurrentUserCall) && !empty($finishCallData['employeeId']) && !empty($callCenterUserData)) {
                        // Отправляем уведомление на фронт о том, что звонок автоматически обработан
                        $this->sendFrontAutoPrepareNotify($callCenterUserData['ID'], $finishCallData['leadId']);

                        // Убираем у оператора признак пост-обработки и ID разговора
                        $this->updateCallCenterUserData(
                            $callCenterUserData['ID'],
                            [
                                'UF_IS_POSTCALL'      => '',
                                'UF_UIS_CALL_SESSION' => '',
                            ]
                        );

                        // Отправляем оператору его новый статус
                        $this->sendEmployeeStatusBySocket($callCenterUserData['ID']);
                    }
                } elseif (!$finishCallData['isTransfer'] && ($finishCallData['finishReason'] == 'no_success_subscriber_call') && empty($finishCallData['lastTalkedEmployeeId']) && $isPredictiveCall && $finishCallData['voiceMailIsDetected']) {
                    $callStatusXmlId = '50000063670';
                    if (!empty($finishCallData['voiceMailIsDetected'])) {
                        $callStatusXmlId = '33333333333';
                    }
                    $newCallStatusData['UF_STATUS_CODE'] = $callStatusXmlId; // Статус "Не дозвонились до клиента"
                    $this->prepareLead(
                        $finishCallData['leadId'],
                        $orderId,
                        Liner::t('Automatic lead processing'),
                        $callStatusXmlId
                    );
                } else {
                    // Обрабатываем Лид автоматически, если оператор не успел его обработать
                    if (empty($callStatusEntityArr['UF_LAST_EDITOR']) && !empty($finishCallData['employeeId']) && !empty($callCenterUserData)) {
                        // Ставим статус в истории дозвонов на "Упущен телефонией" и ждем обработки лида оператором
                        $callISFailedStatusXmlId = 77777777777;
                        $newCallStatusData['UF_STATUS_CODE'] = $callISFailedStatusXmlId;

                        /*
                         * Сразу же планируем дозвон согласно интервалам, не дожидаясь обработки оператором.
                         * если оператор все-таки обработает Лид, то затрет время следующего звонка и это ОК,
                         * иначе - система такой Лид обзвонит самостоятельно ("Упущен телефонией")
                         */
                        $this->prepareLead(
                            $finishCallData['leadId'],
                            $orderId,
                            Liner::t('Automatic lead processing'),
                            $callISFailedStatusXmlId
                        );
                    }

                    if (!empty($isCurrentUserCall) && !empty($callCenterUserData) && !empty($finishCallData['employeeId'])) {
                        // Проставляем признак пост-обработки оператору и убираем ID разговора
                        $this->updateCallCenterUserData(
                            $callCenterUserData['ID'],
                            [
                                'UF_IS_POSTCALL'      => 1,
                                'UF_UIS_CALL_SESSION' => '',
                            ]
                        );

                        // Отправляем уведомление о завершении разговора оператору
                        $this->sendFrontFinishNotify($callCenterUserId, $finishCallData['leadId']);
                        // Отправляем оператору его новый статус
                        $this->sendEmployeeStatusBySocket($callCenterUserData['ID']);
                    }
                }

            } elseif ($isCurrentUserCall && !empty($finishCallData['employeeId']) && !empty($callCenterUserData)) {
                /*
                 * Сразу же планируем дозвон согласно интервалам, не дожидаясь обработки оператором.
                 * если оператор все-таки обработает Лид, то затрет время следующего звонка и это ОК,
                 * иначе - система такой Лид обзвонит самостоятельно ("Упущен телефонией")
                 */

                // На данном этапе нужно отсечь предиктивные неуспешные вызовы
                if (($finishCallData['callSource'] == 'callapi_scenario_call') && ($finishCallData['direction'] == 'out') && (empty($finishCallData['lastTalkedEmployeeId'])) && (empty($finishCallData['talkTimeDuration'])) && ($finishCallData['totalTimeDuration'] == $finishCallData['waitTimeDuration'])) {
                    // Отправляем уведомление на фронт о том, что звонок автоматически обработан
                    $this->sendFrontAutoPrepareNotify($callCenterUserData['ID'], $finishCallData['leadId']);

                    // Убираем у оператора признак пост-обработки и удаляем ID разговора
                    $this->updateCallCenterUserData(
                        $callCenterUserData['ID'],
                        [
                            'UF_IS_POSTCALL'      => '',
                            'UF_UIS_CALL_SESSION' => '',
                        ]
                    );
                } else {
                    // Проставляем признак пост-обработки оператору и удаляем ID разговора
                    $this->updateCallCenterUserData(
                        $callCenterUserData['ID'],
                        [
                            'UF_IS_POSTCALL'      => 1,
                            'UF_UIS_CALL_SESSION' => '',
                        ]
                    );

                    // Отправляем уведомление о завершении разговора оператору
                    $this->sendFrontFinishNotify($callCenterUserData['ID'], $finishCallData['leadId']);
                }

                // Отправляем оператору его новый статус
                $this->sendEmployeeStatusBySocket($callCenterUserData['ID']);

            } elseif ($isPredictiveCall && !$finishCallData['isLost'] && $finishCallData['finishReason'] === 'ai_client_is_not_qualified') {
                $clientIsNotQualifiedStatusId = 50000063679;

                $newCallStatusData['UF_STATUS_CODE'] = $clientIsNotQualifiedStatusId; // Клиент не заинтересован
                $this->prepareLead(
                    $finishCallData['leadId'],
                    $orderId,
                    Liner::t('Automatic lead processing'),
                    $clientIsNotQualifiedStatusId
                );

            // Если это предиктив, в котором абонент бросил трубку на этапе общения с AI
            } elseif (
                $isPredictiveCall &&
                !$finishCallData['isLost'] &&
                ($finishCallData['finishReason'] === 'subscriber_disconnects') &&
                empty($finishCallData['lastTalkedEmployeeId']) &&
                $finishCallData['totalTimeDuration'] &&
                ($finishCallData['waitTimeDuration'] !== $finishCallData['talkTimeDuration'])
            ){
                $callStatusXmlId = 50000063673;  // Бросил трубку
                $newCallStatusData['UF_STATUS_CODE'] = $callStatusXmlId;
                $this->prepareLead(
                    $finishCallData['leadId'],
                    $orderId,
                    Liner::t('Automatic lead processing'),
                    $callStatusXmlId
                );
            } elseif (
                $isPredictiveCall &&
                !$finishCallData['isLost'] &&
                ($finishCallData['finishReason'] === 'operator_channels_busy') &&
                empty($finishCallData['lastTalkedEmployeeId']) &&
                $finishCallData['totalTimeDuration'] &&
                ($finishCallData['waitTimeDuration'] !== $finishCallData['talkTimeDuration'])
            ) {
                // AI поговорил с клиентом, но вызов завершился из-за неудачно делегации предиктива (никого не было из операторов)
                $callStatusXmlId = '88888888888';
                $newCallStatusData['UF_USER_ID'] = 0;
                $newCallStatusData['UF_STATUS_CODE'] = '88888888888';
                $this->prepareLead(
                    $finishCallData['leadId'],
                    $orderId,
                    Liner::t('Automatic lead processing'),
                    $callStatusXmlId
                );
            }

            // Пробуем узнать стоимость звонка
            switch (InstanceHelper::getVatsProviderCode()) {
                case VatProvider::VOX:
                    RabbitProvider::send(
                        RabbitQueue::VOX_CALL_COST_TASKS,
                        [
                            'callResultId'  => $callStatusEntityArr['ID'],
                            'callSessionId' => $finishCallData['callSessionId'],
                        ]
                    );

                break;
                case VatProvider::UIS:
                case VatProvider::CG:
                default:
                    $callTotalCharge = UisApiProvider::getCallSessionTotalCharge($finishCallData['callSessionId']);
                    if (!empty($callTotalCharge)) {
                        $newCallStatusData['UF_CALL_TOTAL_CHARGE'] = $callTotalCharge;
                    }
            }

            // Обновляем информацию в истории звонков
            $callStatusesHlEntityUpdResult = $callResults->updateCallResult(
                intval($callStatusEntityArr['ID']),
                $newCallStatusData
            );

            if (InstanceHelper::isVoxVatsProvider()) {
                if (!empty($callCenterUserData['ID']) && !empty($finishCallData['leadId']) && !empty($callStatusEntityArr['ID']) && !empty($finishCallData['callSessionId']) && !empty($finishCallData['finishCallInitiator'])) {
                    $callResults->storeToCallHangup(
                        intval($callCenterUserData['ID']),
                        intval($finishCallData['leadId']),
                        intval($callStatusEntityArr['ID']),
                        intval($finishCallData['callSessionId']),
                        strval($finishCallData['finishCallInitiator'])
                    );
                }
            }

            if (!empty($callStatusesHlEntityUpdResult)) {

                SocketService::sendLeadUpdateEvent(
                    leadId: $finishCallData['leadId'],
                    eventCode: SocketEventRegistry::CALL_FINISHED,
                    eventData: ['callSessionId' => $finishCallData['callSessionId']]
                );

                return IO::jsonDeadResponse('success', true);
            }
        }

        return IO::jsonDeadResponse('ok', true);
    }

    /**
     * Получаем последний sessionId по лиду
     *
     * @param int $leadId
     *
     * @return int
     * */
    private function getLastCallSessionId(int $leadId) : int
    {
        if (empty($leadId)) {
            return 0;
        }

        $callResults = new Callresults();

        // Refactored
        $callStatusEntity = $callResults->getCallResultsList(
            ['ID', 'UF_CALL_SESSION_ID'],
            [
                'UF_LEAD_ID' => $leadId,
            ],
            1
        );

        return !empty(intval($callStatusEntity['UF_CALL_SESSION_ID'])) ? intval(
            $callStatusEntity['UF_CALL_SESSION_ID']
        ) : 0;
    }

    /**
     * Функция для проверки оператора если он пропускает исходящие звонки и их 3 штуки подряд и сменяем ему статус на
     * "нет на работе"
     *
     * @return void
     */
    public function checkOperatorForPassOutgoing()
    {
        $maxPassOutgoing = 3;

        $quantityPassOutgoing = 0;

        $user = new User();

        $callResults = new Callresults();

        $userData = $user->getUser();

        if (!empty($userData['ID'])) {
            // Refactored
            $res = $callResults->getCallResultsList(
                [
                    'ID',
                    'UF_STATUS_CODE',
                    'UF_USER_ID',
                    'UF_DIRECTION',
                ],
                [
                    'UF_USER_ID' => $userData['ID'],
                ],
                $maxPassOutgoing
            );

            //while ($item = $res->fetch())
            foreach ($res as $item) {
                if ($item['UF_STATUS_CODE'] == 88888888888 && $item['UF_DIRECTION'] == 1) {
                    $quantityPassOutgoing++;
                }
            }

            $employeeStatusMap = $this->getEmployeeStatusesMap(false);

            if ($quantityPassOutgoing === $maxPassOutgoing && !empty($employeeStatusMap["not_at_work"])) {
                $this->changeEmployeeStatus($employeeStatusMap['not_at_work'], $userData['ID']);
                $this->sendEmployeeStatusBySocket($userData['ID']);
            }
        }
    }

    /**
     * Смена статуса пользователя только в Лайнре в uis всегда доступный
     * При смене на доступный вызвается dialer
     *
     * @param $newStatusId
     * @param $userId
     *
     * @return bool
     */
    public function changeEmployeeStatus($newStatusId, $userId)
    {
        if (empty($newStatusId) || empty($userId)) {
            return false;
        }

        $res = $this->updateCallCenterUserData(
            $userId,
            [
                'UF_UIS_STATUS'       => $newStatusId,
                'UF_IS_POSTCALL'      => '',
                'UF_UIS_CALL_SESSION' => '',
            ]
        );

        if (!$res) {
            return false;
        }

        $availableCallCenterStatus = $this->getAvailableCallStatus();

        if ($newStatusId == $availableCallCenterStatus['UF_UIS_ID']) {
            $this->rabbitDialer();
        }

        return true;
    }

    /**
     * Отправляем уведомление на фронт о завершении вызова
     *
     * @param $userId
     * @param $leadId
     *
     * @return void
     */
    public function sendFrontFinishNotify($userId, $leadId): void
    {
        // Отправляем уведомление на фронт о завершении вызова
        SocketProvider::request(
            route: '/' . SocketEventRegistry::FINISHED_CALL . '/',
            method: HTTPMethod::POST,
            body: [
                'channelId' => 'ch-' . $userId,
                'leadId'    => $leadId,
            ]
        );
    }

    public function storeToCallHangup() : array
    {
        $request = IO::getRequest();

        $callId = $request['call_id'];
        $leadId = $request['lead_id'];
        $operatorId = $request['operator_id'];
        $callSessionId = $request['call_session_id'];
        $hangup = $request['hangup'];
        $error = false;
        $status = true;

        switch (InstanceHelper::getVatsProviderCode()) {
            case VatProvider::UIS:
            case VatProvider::CG:
            default:
                try {
                    DB::add(
                        Callresults::DB_TABLE_NAME_HANGUPS,
                        [
                            'UF_CALL_ID'         => $callId,
                            'UF_LEAD_ID'         => $leadId,
                            'UF_OPERATOR_ID'     => $operatorId,
                            'UF_CALL_TIMESTAMP'  => time(),
                            'UF_CALL_SESSION_ID' => $callSessionId,
                            'UF_HANGUP'          => (int) $hangup,
                        ]
                    );
                } catch (Exception $e) {
                    $status = false;
                    $error = $e->getMessage();
                }
        }

        return [
            "status"    => $status,
            "data"      => [
                'UF_CALL_ID'         => $callId,
                'UF_LEAD_ID'         => $leadId,
                'UF_OPERATOR_ID'     => $operatorId,
                'UF_CALL_SESSION_ID' => $callSessionId,
                'UF_HANGUP'          => $hangup,
            ],
            "error"     => $error,
            "cache_hit" => null,
        ];
    }

    /**
     * Смена статуса оператору
     * @post $_POST['status_id']
     *
     * @tariffs Проверяет на кол-во активных операторов
     * @api
     */
    protected function changeEmployeeStatusAction()
    {
        $newStatusId = (int) ($_POST['status_id']);

        if (empty($newStatusId)) {
            return IO::jsonDeadResponse(Liner::t('Required parameters not passed'));
        }

        $activeCallCenterUsersCount = $this->getOnlineOperatorsTotalCount();

        $employeeStatusMap = $this->getEmployeeStatusesMap();

        if ($newStatusId != $employeeStatusMap['not_at_work'] && Plan::limitExceeded('other_functions', 'max_count_active_call_center_users', $activeCallCenterUsersCount)) {
            return IO::jsonDeadResponse(Liner::t('The maximum number of operators on the line for your tariff has been reached!'));
        }

        $userId = Liner::userId();

        $changeStatusRes = $this->changeEmployeeStatus($newStatusId, $userId);

        $this->sendEmployeeStatusBySocket($userId);

        if (empty($changeStatusRes)) {
            return IO::jsonDeadResponse(Liner::t('An error occurred while changing status'));
        }

        return IO::jsonDeadResponse(Liner::t('Status changed successfully'), true);
    }

    /**
     * Общее кол-во онлайн операторов
     *
     * @return int
     */
    public function getOnlineOperatorsTotalCount()
    {
        $employeeStatusMap = $this->getEmployeeStatusesMap(true);

        $user = new User();

        $rsUsers = $user->getActiveCallCenterUsersMap();

        $onlineOperatorsTotalCount = 0;

        $phoneFieldCode = match (InstanceHelper::getVatsProviderCode()) {
            VatProvider::VOX => 'UF_VOX_USER_NAME',
            default => 'UF_UIS_ID',
        };

        foreach ($rsUsers as $userData) {
            if (empty($userData[$phoneFieldCode])) {
                continue;
            }

            if (!empty($userData['UF_UIS_STATUS']) && !empty($employeeStatusMap[$userData['UF_UIS_STATUS']])) {
                switch ($employeeStatusMap[$userData['UF_UIS_STATUS']]) {
                    case 'available':
                    case 'active_call':
                    case 'post_call':
                    case 'break':
                    case 'tech_break':
                        $onlineOperatorsTotalCount++;
                    break;
                }
            }
        }

        return $onlineOperatorsTotalCount;
    }

    /**
     * Сохранение результат при завершение оператором звонка
     * Если это тренеровочный лид Убираем у оператора признак пост-обработки и ID разговора и вызваем dialer
     * Если не передана сессия звонка внешняя, или внутрення, то пытаемся получить ID последнего звонка
     * Если лид из Подбора, при этом не передан ID Нового Заказа и лид пытаются сделать Целевым, то нужно отдать ошибку
     * Снимаем флаг пост-обработки у оператора
     * Убедимся, что запись звонка не пришла раньше, чем пользователь обработал лид и в ней не поставился статус "Не
     * дождался соединения с ОП" Обновляем статус лида, в зависимости от полученного статуса звонка Вызываем rabbit
     * hook_after_save_call_result Вызывем dialer
     * @post $_POST['call_status'] $_POST['lead_id'] $_POST['order_id'] $_POST['uis_call_id'] $_POST['local_call_id']
     *     $_POST['selection_order_id'] $_POST['comment']
     *
     * @api
     */
    protected function saveCallResult()
    {
        $request = IO::getRequest();

        $user = new User();

        $callResults = new Callresults();

        // Достаем нужные параметры
        $userData = $user->getUser();

        $callStatusXmlId = (string) ($request['call_status']);
        $leadId = (int) ($request['lead_id']);
        $orderId = (int) ($request['order_id']);
        //todo общее название
        $uisCallId = (int) ($request['uis_call_id']);
        $localCallId = (int) ($request['local_call_id']);
        $selectionOrderId = (int) ($request['selection_order_id']);
        $selectionObjectId = (int) ($request['selection_object_id']);

        $isTrainingLead = ($leadId == 1);
        if ($isTrainingLead) {
            // Убираем у оператора признак пост-обработки и ID разговора
            $this->updateCallCenterUserData(
                $userData['ID'],
                [
                    'UF_IS_POSTCALL'      => '',
                    'UF_UIS_CALL_SESSION' => '',
                ]
            );

            $this->sendEmployeeStatusBySocket($userData['ID']);
            $this->rabbitDialer(2);

            return IO::jsonDeadResponse(Liner::t('Lead processing completed'), true);
        }

        $leadData = (new Leads())->getLeadDataById($leadId, ['ID', 'UF_LEAD_TYPE']);
        $isSelectionLead = ($leadData['UF_LEAD_TYPE'] ?? false) == 'selection';

        if (empty($callStatusXmlId) || empty($leadId)) {
            IO::jsonDeadResponse(Liner::t('Required parameters not passed'));
        }

        //  Если не передана сессия звонка внешняя, или внутрення, то пытаемся получить ID последнего звонка
        if (empty($uisCallId) || empty($localCallId)) {
            $leads = new Leads();

            // Refactored
            $leadData = $leads->getLeadList(
                [
                    'ID',
                    'UF_UIS_CALL_ID',
                    'UF_UIS_LAST_CALL_ID',
                    'UF_LOCAL_CALL_ID',
                    'UF_LOCAL_LAST_CALL_ID',
                ],
                [
                    'ID' => $leadId,
                ],
                1
            );

            if (!empty($leadData)) {
                if (empty($uisCallId)) {
                    if (!empty($leadData['UF_UIS_CALL_ID'])) {
                        $uisCallId = (int) ($leadData['UF_UIS_CALL_ID']);
                    } elseif (!empty($leadData['UF_UIS_LAST_CALL_ID'])) {
                        $uisCallId = (int) ($leadData['UF_UIS_LAST_CALL_ID']);
                    }
                }

                if (empty($localCallId)) {
                    if (!empty($leadData['UF_LOCAL_CALL_ID'])) {
                        $localCallId = (int) ($leadData['UF_LOCAL_CALL_ID']);
                    } elseif (!empty($leadData['UF_LOCAL_LAST_CALL_ID'])) {
                        $localCallId = (int) ($leadData['UF_LOCAL_LAST_CALL_ID']);
                    }
                }
            }
        }

        if (empty($uisCallId)) {
            IO::jsonDeadResponse(Liner::t('Failed to identify the call'));
        }

        // Последняя попытка идентифицировать вызов
        if (empty($localCallId) && !empty($uisCallId)) {
            // Refactored
            $callStatusRecordArr = $callResults->getCallResultsList(
                ['ID'],
                [
                    'UF_CALL_SESSION_ID' => $uisCallId,
                ],
                1
            );

            if (!empty($callStatusRecordArr)) {
                $localCallId = $callStatusRecordArr['ID'];
            }
        }

        if (empty($uisCallId) || empty($localCallId)) {
            IO::jsonDeadResponse(Liner::t('Failed to identify the call'));
        }

        $statusesMap = $this->getStatusesMap();

        if ($isSelectionLead && (($statusesMap[$callStatusXmlId] == 'dark') || ($statusesMap[$callStatusXmlId] == 'already-success'))) {
            $orderId = $selectionOrderId;

            if (empty($orderId) && $callStatusXmlId == '50000064100') {
                // Refactored
                $callStatusRecordArr = $callResults->getCallResultsList(
                    ['ID', 'UF_SELECTION_ORDER_ID'],
                    [
                        '>UF_SELECTION_ORDER_ID'  => 0,
                        '>UF_SELECTION_OBJECT_ID' => 0,
                        'UF_LEAD_ID'              => $leadId,
                    ],
                    1
                );

                if (!empty($callStatusRecordArr['UF_SELECTION_ORDER_ID'])) {
                    $orderId = $callStatusRecordArr['UF_SELECTION_ORDER_ID'];
                }
            }
        }

        // Если лид из Подбора, при этом не передан ID Нового Заказа и лид пытаются сделать Целевым, то нужно отдать ошибку
        if ($isSelectionLead && empty($orderId) && (($statusesMap[$callStatusXmlId] == 'dark') || ($statusesMap[$callStatusXmlId] == 'already-success'))) {
            return IO::jsonDeadResponse(Liner::t('First select an Object'));
        }

        // Снимаем флаг пост-обработки у оператора
        $this->updateCallCenterUserData(
            $userData['ID'],
            [
                'UF_IS_POSTCALL' => '',
            ]
        );

        $this->sendEmployeeStatusBySocket($userData['ID']);

        // Готовим массив для истории звонков
        $newCallStatusData = [];

        $newCallStatusData['UF_SELECTION_ORDER_ID'] = $selectionOrderId;
        $newCallStatusData['UF_SELECTION_OBJECT_ID'] = $selectionObjectId;

        // Refactored
        $callStatusData = $callResults->getCallResultsList(['*'], ['ID' => intval($localCallId)], 1);

        if (empty($callStatusData['ID'])) {
            IO::jsonDeadResponse(Liner::t('Failed to get ID from conversation history'));
        }

        // Убедимся, что запись звонка не пришла раньше, чем пользователь обработал лид
        // И в ней не поставился статус "Не дождался соединения с ОП"
        if (empty($callStatusData['UF_STATUS_CODE']) || ($callStatusData['UF_STATUS_CODE'] != '22222222222' && $callStatusData['UF_STATUS_CODE'] != '50000063675')) {
            $newCallStatusData['UF_STATUS_CODE'] = $callStatusXmlId;
            $newCallStatusData['UF_LAST_EDITOR'] = $userData['ID'];
        }

        $newCallStatusData['UF_LEAD_ID'] = $leadId;
        $newCallStatusData['UF_USER_UPDATE_DATE'] = Moment::create(toTz: TZ::UTC, dateFormatType: DF::DB_FULL);

        $callStatusesHlEntityUpdResult = $callResults->updateCallResult(intval($localCallId), $newCallStatusData);

        if (empty($callStatusesHlEntityUpdResult)) {
            IO::jsonDeadResponse(Liner::t('Failed to save the result of processing the conversation'));
        }

        // Обновляем статус лида, в зависимости от полученного статуса звонка
        if ($callStatusData['UF_STATUS_CODE'] != '22222222222') {
            $res = $this->prepareLead($leadId, $orderId, '', $callStatusXmlId);

            $this->isTransfer($leadId, $uisCallId);
        }

        // Отложенное событие
        $this->afterSaveCallResultEvent($callStatusData['ID']);

        // Каждый завершенный звонок порождает 2 вызова диалера для заполнения всех свободных операторов
        $this->rabbitDialer(2);

        return IO::jsonDeadResponse(Liner::t('Lead processing completed'), true, $res);
    }

    public function getPhonesModes(): array
    {
        $arrResult = [
            'default' => ['name' => Liner::t('Default mode'), 'colorHex' => '#4bbf73'],
            'outgoing-only' => ['name' => Liner::t('outgoing-only'), 'colorHex' => '#3f80ea'],
            'incoming-only' => ['name' => Liner::t('incoming-only'), 'colorHex' => '#3f80ea'],
        ];

        if (Plan::isAvailable('mod_predictive_mode'))
            $arrResult['predictive'] = ['name' => Liner::t('predictive'), 'colorHex' => '#3f80ea'];

        return $arrResult;
    }

    /**
     * @param int      $orderId
     * @param int|null $leadId
     * @param          $leadPhoneNumber
     *
     * @return SipEndpoint|null
     */
    public function getOutgoingOrderPhoneNumber(int $orderId = 0, int $leadId = null, $leadPhoneNumber = ''): ?SipEndpoint
    {
        if (!$orderId && !$leadId) {
            return null;
        }

        $orderPhoneNumbersIds = (new Orders())->getOrderPhoneIds($orderId, true);

        if (empty($orderPhoneNumbersIds)) {

            $defaultPhoneData = SipEndpointRepository::getDefault();

            if ($defaultPhoneData instanceof SipEndpoint) {
                return $defaultPhoneData;
            }
        } else {

            $callResults = (new Callresults());

            $phonesList = SipEndpointRepository::find(filter: ['id' => $orderPhoneNumbersIds, 'outgoing' => true, 'orderId' => [0, $orderId]]);

            if (!empty($phonesList)) {
                $availableForOutgoing = [];
                foreach ($phonesList as $phoneData) {

                    // Check active calls with this numbers
                    $activeCallCount = $callResults->getActiveCallCountByPhoneNumber($phoneData);

                    if ($activeCallCount >= (int) $phoneData->channels) {
                        continue;
                    }

                    $availableForOutgoing[] = $phoneData;
                }

                if (!empty($availableForOutgoing) && !empty($leadPhoneNumber)) {
                    $availableForOutgoing = $this->filterOutgoingPhonesByLeadPhone($availableForOutgoing, $leadPhoneNumber);
                }

                if (empty($availableForOutgoing)) {

                    $defaultPhoneData = SipEndpointRepository::getDefault();

                    if ($defaultPhoneData instanceof SipEndpoint)
                        return $defaultPhoneData;
                }

                $orderScheme = (new Orders())->getOrderPhoneUsageScheme($orderId);

                switch ($orderScheme) {
                    case 'random_without_repetition':
                        return $this->getUniqueRandomPhoneNumber($leadId, $availableForOutgoing);
                    case 'even_loaded':
                        return $this->getEvenLoadedPhoneNumber($leadId, $availableForOutgoing);
                    case 'even_loaded_daily':
                        return $this->getEvenLoadedPhoneNumber($leadId, $availableForOutgoing, 'day');
                    case 'random_default':
                    default:
                        return SipEndpointService::getRandomPhoneNumberByPhoneData($availableForOutgoing);
                }
            }
        }

        return null;
    }

    /**
     * @param SipEndpoint|null $phoneData
     *
     * @return bool
     */
    protected function incomingIsAllowedByClearPhoneNumber(?SipEndpoint $phoneData)
    {
        if (!$phoneData instanceof SipEndpoint) {
            return false;
        }

        $activeCallCount = (new Callresults())->getActiveCallCountByPhoneNumber($phoneData);

        if ($activeCallCount >= $phoneData->channels) {
            return false;
        }

        if (!$phoneData->incoming)
            return false;

        return true;
    }

    /**
     * Функция возращет телефон исходя из входящих звонков лида чтобы не было повторов,
     * если звонки пошли по второму кругу от кол-ва прикрепленных номеров к заказу выбираем любой номер
     * @param int   $leadId
     * @param array $phoneDataItems
     *
     * @return SipEndpoint|null
     */
    protected function getUniqueRandomPhoneNumber(int $leadId, array $phoneDataItems): ?SipEndpoint
    {
        if (!$leadId || empty($phoneDataItems)) {
            return null;
        }

        // Находим запись в истории звонков, связанную с этой сессией
        // Refactored
        $callsResult = (new Callresults())->getCallResultsList(
            ['*'],
            [
                'UF_DIRECTION' => 1,
                'UF_LEAD_ID' => $leadId,
            ]
        );

        if (!empty($callsResult)) {

            $restOfTheNewCircleOfCalls = count($callsResult) % count($phoneDataItems);

            if ($restOfTheNewCircleOfCalls > 0) {
                $usedPhoneArr = [];

                foreach ($callsResult as $keyCall => $valueCall) {
                    if ($valueCall['sipEndpointId'] && $keyCall < $restOfTheNewCircleOfCalls && !in_array($valueCall['sipEndpointId'], $usedPhoneArr)) {
                        $usedPhoneArr[] = $valueCall['sipEndpointId'];
                    }
                }

                foreach ($phoneDataItems as $phone) {
                    if ($phone instanceof SipEndpoint && !in_array($phone->id, $usedPhoneArr)) {
                        return $phone;
                    }
                }
            }
        }

        return SipEndpointService::getRandomPhoneNumberByPhoneData($phoneDataItems);
    }

    /**
     * @param        $leadId
     * @param array  $phoneDataItems
     * @param string $period
     *
     * @return SipEndpoint|null
     * @throws Exception
     */
    protected function getEvenLoadedPhoneNumber($leadId, array $phoneDataItems, string $period = ''): ?SipEndpoint
    {
        if (!$leadId || empty($phoneDataItems)) {
            return null;
        }

        // Извлекаем номера из массива телефонов
        $phoneDataByNumber = $phoneNumbersIds = $attemptsByPhoneNumber = $leadsByPhoneNumber = [];
        foreach ($phoneDataItems as $phoneDataItem) {

            $phoneDataByNumber[$phoneDataItem->id] = $phoneDataItem;
            $phoneNumbersIds[] = $phoneDataItem->id;
            $attemptsByPhoneNumber[$phoneDataItem->id] = 0;
            $leadsByPhoneNumber[$phoneDataItem->id] = [];
        }

        $callsFilter = [
            'UF_DIRECTION' => 1,
            'sipEndpointId' => $phoneNumbersIds
        ];

        if ($period === 'day') {
            $callsFilter['>=UF_DATE'] = Moment::create(toTz: TZ::UTC, dateFormatType: DF::DB_DATE);
        }

        $callsResult = (new Callresults())->getCallResultsList(
            ['ID', 'sipEndpointId', 'UF_LEAD_ID'],
            $callsFilter
        );

        // Counting stats by phone number
        foreach ($callsResult as $callItem) {
            $phn = $callItem['sipEndpointId'];
            $lId = $callItem['UF_LEAD_ID'];

            if (isset($attemptsByPhoneNumber[$phn])) {
                $attemptsByPhoneNumber[$phn]++;
            }

            if (isset($leadsByPhoneNumber[$phn][$lId])) {
                $leadsByPhoneNumber[$phn][$lId]++;
            } else {
                $leadsByPhoneNumber[$phn][$lId] = 1;
            }
        }

        // Sorting phone numbers by total count
        asort($attemptsByPhoneNumber);

        $mostSuitablePhoneNumbers = [];
        foreach ($attemptsByPhoneNumber as $phn => $cnt) {
            // If we haven't attempts with most suitable number by this lead
            if (!isset($leadsByPhoneNumber[$phn][$leadId])) {
                $mostSuitablePhoneNumbers[$phn] = $cnt;
            } else {
                $mostSuitablePhoneNumbers[$phn] = $cnt + $leadsByPhoneNumber[$phn][$leadId];
            }
        }

        asort($attemptsByPhoneNumber);

        $mostSuitablePhoneNumber = array_key_first($mostSuitablePhoneNumbers);

        return $phoneDataByNumber[$mostSuitablePhoneNumber] instanceof SipEndpoint  ? $phoneDataByNumber[$mostSuitablePhoneNumber] : null;
    }

    /**
     * Функция определения приоритетных номеров для исходящего звонка
     * @param array $phonesLead
     * @param string $phoneClient
     * @return array
     */
    //@todo LINER-700 если будет sip?
    protected function filterOutgoingPhonesByLeadPhone(array $availableForOutgoing, string $phoneClient): array
    {
        $leads = new Leads();

        $res = [];

        $thisCodeNameCountry = $leads->nameCodeCountryByPhone($phoneClient);

        foreach ($availableForOutgoing as $phone) {
            if (
                (
                    $phone->isPTSN() &&
                    $thisCodeNameCountry !== ''
                    && $thisCodeNameCountry == $leads->nameCodeCountryByPhone($phone->extractPhoneNumber())
                )
                ||
                ($thisCodeNameCountry == '')
            ) {
                $res[] = $phone;
            }
        }

        return (!empty($res)) ? $res : $availableForOutgoing;
    }
}
