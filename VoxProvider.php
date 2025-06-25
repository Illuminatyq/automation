<?php

namespace App\Providers;

use App\Constants\Enum\Events;
use App\Constants\Enum\HTTPMethod;
use App\Constants\Path;
use App\Core\Cache;
use App\Core\IO;
use App\Events\EventManager;
use App\Exceptions\System\Config\MissingConfigException;
use App\Exceptions\System\CurlException;
use App\Exceptions\System\Provider\VoxException;
use App\Exceptions\System\Provider\WazzupException;
use App\Helpers\InstanceHelper;
use App\Objects\HTTPRequest;
use App\Objects\SipEndpoint;
use DateTime;
use Throwable;
use Voximplant\Resources\Params\AddUserParams as AddUserParams;
use Voximplant\Resources\Params\CreateSipRegistrationParams;
use Voximplant\Resources\Params\DelUserParams as DelUserParams;
use Voximplant\Resources\Params\GetCallHistoryParams as GetCallHistoryParams;
use Voximplant\Resources\Params\GetNewPhoneNumbersParams;
use Voximplant\Resources\Params\GetPhoneNumberCategoriesParams;
use Voximplant\Resources\Params\GetPhoneNumberRegionsParams;
use Voximplant\Resources\Params\GetUsersParams as GetUsersParams;
use Voximplant\Resources\Params\IsAccountPhoneNumberParams;
use Voximplant\Resources\Params\StartScenariosParams as StartScenariosParams;
use Voximplant\Resources\Params\UpdateSipRegistrationParams;
use Voximplant\VoximplantApi as VoxImplantApi;


# TODO: refactor this
final class VoxProvider extends BaseProvider
{
    protected const string CONFIG_FILE = Path::CONFIG . 'vox.json';
    protected VoximplantApi $voxApi;

    //protected string $locale;

    /**
     * @throws MissingConfigException
     */
    public function __construct()
    {
        if (InstanceHelper::isVoxVatsProvider()) {
            if (!file_exists(self::CONFIG_FILE)) {
                throw new MissingConfigException( self::CONFIG_FILE);
            }

            $this->voxApi = new VoximplantApi(self::CONFIG_FILE);

//            switch (Locale::current()){
//                case 'ru':
//                    $this->locale = 'RU';
//                    break;
//                case 'gb':
//                    $this->locale = 'EN';
//                    break;
//            }
        }
    }

    /**
     * Отправляем запрос на Management URL для с командой завершения предиктивного вызова
     *
     * @param string $callManagementLink
     *
     * @return void
     * @throws VoxException
     */
    public function finishPredictiveCall(string $callManagementLink) : void
    {
        $httpRequest = new HTTPRequest(
            url: $callManagementLink,
            method: HTTPMethod::POST
        );

        $httpRequest->withJsonBody(['method' => 'predictive_terminate', 'data' => []]);

        try {
            $httpRequest->execute();
        } catch (Throwable $e) {
            throw new VoxException($e);
        }
    }

    /**
     * Создает нового пользователя в VoxImplant,
     * в случае успеха, возвращает его ID
     *
     * @param string $userName
     * @param string $userPass
     * @param string $displayName
     *
     * @return int
     */
    public function createUser(string $userName, string $userPass, string $displayName) : int
    {
        $params = $this->setAddUsersParams([
            'application_name' => IO::readEnv('CONF_VOX_APP_NAME'), 'user_name' => $userName, 'user_password' => $userPass, 'user_display_name' => $displayName, 'user_active' => 1,
        ]);

        $res = $this->voxApi->Users->AddUser($params);

        return $res->user_id;
    }

    /**
     * Устанавливает параметры для запроса на добавление пользователя в VoxImplant
     *
     * @param array $params
     *
     * @return AddUserParams
     */
    protected function setAddUsersParams(array $params = []) : AddUserParams
    {
        $addUserParams = new AddUserParams();

        if (!empty($params)) {
            foreach ($params as $paramKey => $paramValue) {
                $addUserParams->$paramKey = $paramValue;
            }
        }

        return $addUserParams;
    }

    /**
     * Removes vox implant user
     *
     * @param int $voxUserId
     *
     * @return int
     */
    public function deleteUser(int $voxUserId) : int
    {
        $params = $this->setDelUsersParams([
            'application_name' => IO::readEnv('CONF_VOX_APP_NAME'), 'user_id' => [$voxUserId],
        ]);

        $res = $this->voxApi->Users->DelUser($params);

        return $res->result;
    }

    /**
     * Устанавливает параметры для запроса на удаление пользователя в VoxImplant
     *
     * @param array $params
     *
     * @return DelUserParams
     */
    protected function setDelUsersParams(array $params = []) : DelUserParams
    {
        $delUserParams = new DelUserParams();

        if (!empty($params)) {
            foreach ($params as $paramKey => $paramValue) {
                $delUserParams->$paramKey = $paramValue;
            }
        }

        return $delUserParams;
    }

    /**
     * Считает итоговую стоимость звонка по ID сессии
     *
     * @param int $callSessionId
     *
     * @return null|float
     */
    public function getTotalCostBySessionId(int $callSessionId): ?float
    {
        $callsIsset = $recordsIsset = $serviceIsset = false;
        $totalCost = 0.0;

        $callSessionInfo = $this->getCallHistoryBySessionId($callSessionId);

        if (!empty($callSessionInfo['calls'])) {
            $callsIsset = true;
            foreach ($callSessionInfo['calls'] as $callItem) {
                $totalCost += $callItem['cost'];
            }
        }

        if (!empty($callSessionInfo['records'])) {
            $recordsIsset = true;
            foreach ($callSessionInfo['records'] as $recordItem) {
                $totalCost += $recordItem['cost'];
            }
        }

        if (!empty($callSessionInfo['other_resource_usage'])) {
            $serviceIsset = true;
            foreach ($callSessionInfo['other_resource_usage'] as $otherItem) {
                $totalCost += $otherItem['cost'];
            }
        }

        return ($callsIsset || $recordsIsset || $serviceIsset) ? $totalCost : null;
    }

    /**
     * Возвращает полную информацию о вызове по ID сессии звонка
     *
     * @param int $callSessionId
     *
     * @return array
     */
    public function getCallHistoryBySessionId(int $callSessionId): array
    {
        $maxDateTime = new DateTime();
        $maxDateTime->setTime('23', '59', '59');
        $minDateTime = clone $maxDateTime;
        $minDateTime->modify('- 6 month');

        $params = $this->setCallHistoryParams([
            'application_name' => IO::readEnv('CONF_VOX_APP_NAME'), 'from_date' => $minDateTime->format('Y-m-d H:i:s'), 'to_date' => $maxDateTime->format('Y-m-d H:i:s'), 'call_session_history_id' => $callSessionId, 'count' => 1, 'with_calls' => true, 'with_records' => true, 'with_other_resources' => true,
        ]);

        $res = $this->voxApi->History->GetCallHistory($params);

        return (!empty($res->result[0])) ? $res->result[0] : [];
    }

    /**
     * Устанавливает параметры для запроса истории вызовов VoxImplant
     *
     * @param array $params
     *
     * @return GetCallHistoryParams
     */
    protected function setCallHistoryParams(array $params = []): GetCallHistoryParams
    {
        $getCallHistoryParams = new GetCallHistoryParams();

        if (!empty($params)) {
            foreach ($params as $paramKey => $paramValue) {
                $getCallHistoryParams->$paramKey = $paramValue;
            }
        }

        return $getCallHistoryParams;
    }

    /**
     * Инициализирует новый исходящий звонок в Предиктивном режиме
     * возвращает массив, состоящий из ID сессии звонка и ссылки на управление вызовом
     *
     * @param string            $leadPhone
     * @param SipEndpoint $sipEndpoint
     * @param int               $leadId
     * @param string            $callerIdForTransferPhone
     * @param string            $clientCallScript
     * @param bool              $aiIsAllowed
     * @param string|null       $aiPrompt
     *
     * @return array
     */
    public function predictiveOutgoingCall(
        string      $leadPhone,
        SipEndpoint $sipEndpoint,
        int         $leadId,
        string      $callerIdForTransferPhone,
        string      $clientCallScript = '',
        bool        $aiIsAllowed = false,
        ?string     $aiPrompt = ''
    ) : array
    {
        $result = [
            'callSessionId' => 0, 'callManagementLink' => '',
        ];

        $voxAppName = IO::readEnv('CONF_VOX_APP_NAME');
        $voxPredictiveRuleId = (int) IO::readEnv('CONF_VOX_PREDICTIVE_RULE_ID');

        if (empty($leadPhone) || !$leadId || empty($voxAppName) || !$voxPredictiveRuleId || empty($callerIdForTransferPhone)) {
            return $result;
        }

        $customData = array_merge(
            $this->getStaticInputData(false),
            [
                'lead_phone' => $leadPhone,
                'sip_endpoint' => [
                    'type' => $sipEndpoint->connectionType,
                    'params' => $sipEndpoint->params,
                ],
                'lead_id' => $leadId,
                'display_name' => 'Lead #' . $leadId,
                'count' => 1,
                'caller_id_for_transfer_phone' => $callerIdForTransferPhone,
                'client_call_script' => $clientCallScript,
                'ai_is_allowed' => $aiIsAllowed,
                'ai_prompt' => $aiPrompt,
            ]
        );

        $res = $this->startScenarioCall([
            'application_name' => $voxAppName, 'rule_id' => $voxPredictiveRuleId, 'script_custom_data' => $customData,
        ]);

        if ($res->result && $res->call_session_history_id && $res->media_session_access_secure_url) {
            $result = [
                'callSessionId' => $res->call_session_history_id, 'callManagementLink' => $res->media_session_access_secure_url,
            ];
        }

        return $result;
    }

    /**
     * Возвращает массив с дефолтными параметрами для инициализации вызова
     * используется как при инициализации вызовов из Лайнера, так и для входящих вызовов
     * При входящем вызове вызывается со стороны VoxImplant
     *
     * @param bool $returnJson
     *
     * @return array|void
     */
    public function getStaticInputData(bool $returnJson = true): array
    {
        $hostUrl = InstanceHelper::getHttpHost(forceMain: true);

        $res = [
            'callback_urls' => [
                'call_record' => $hostUrl . '/api/?controller=Vats&method=rabbitSaveCallRecord',
                'leg_is_connected' => $hostUrl . '/api/?controller=Vats&method=legIsConnected',
                'leg_is_disconnected' => $hostUrl . '/api/?controller=Vats&method=legIsDisconnected',
                'finish_call' => $hostUrl . '/api/?controller=Vats&method=finishCallHook',
                'incoming_call_started' => $hostUrl . '/api/?controller=Vats&method=internalStartCall',
                'delegate_predictive' => $hostUrl . '/api/?controller=Vats&method=delegatePredictiveCall',
                'predictive_ai_events' => $hostUrl . '/api/?controller=Vats&method=predictiveAiEvents',
            ],
            'recorder_params' => [
                'hd_audio' => false,
                'stereo' => false,
            ],
            'incoming_params' => [
                'attempts_max' => 12,
                'attempts_delay' => 5000, // 1 sec = 1000
            ],
            'sounds' => [
                'hold' => $hostUrl . '/' . Path::SOUNDS_PROGRESS . 'classic.mp3',
                'fail_transfer' => $hostUrl . '/' . Path::SOUNDS_PROGRESS . 'fail-call.mp3',
                'beeps' => $hostUrl . '/' . Path::SOUNDS_PROGRESS . 'beeps.mp3',
                'busy' => $hostUrl . '/' . Path::SOUNDS_PROGRESS . 'busy.mp3',
                'black' => $hostUrl . '/' . Path::SOUNDS_PROGRESS . 'black.mp3',
                'off_hours' => $hostUrl . '/' . Path::SOUNDS_PROGRESS . 'off-hours.mp3',
                'busy_delay' => $hostUrl . '/' . Path::SOUNDS_PROGRESS . 'classic.mp3',
            ],
        ];

        EventManager::dispatch(Events::VOX_AFTER_STATIC_INPUT_DATA, $res);

        if (!$returnJson) {
            return $res;
        }

        IO::jsonDeadResponse('', true, $res);
    }

    /**
     * Запускает сценарий в VoxImplant
     * В случае успеха, возвращает ID сессии звонка
     *
     * @param array $scenarioData
     *
     * @return int
     */
    public function startScenarioCall(array $scenarioData): object
    {
        $params = $this->setScenarioParams($scenarioData);

        return $this->voxApi->Scenarios->StartScenarios($params);
    }

    /**
     * Устанавливает параметры для запуска сценария в VoxImplant
     *
     * @param array $params
     *
     * @return StartScenariosParams
     */
    protected function setScenarioParams(array $params = []): StartScenariosParams
    {
        $scenarioParams = new StartScenariosParams();

        if (!empty($params)) {
            foreach ($params as $paramKey => $paramValue) {
                if ($paramKey === 'script_custom_data') {
                    $scenarioParams->script_custom_data = $this->constructScriptCustomData($paramValue);
                } else {
                    $scenarioParams->$paramKey = $paramValue;
                }
            }
        }

        return $scenarioParams;
    }

    /**
     * Преобразует customData в нужный вид для установки в параметрах сценария VoxImplant
     *
     * @param mixed $customData
     *
     * @return string
     */
    protected function constructScriptCustomData($customData): string
    {
        if (is_array($customData)) {
            $customData = json_encode($customData);
        }

        return (string)$customData;
    }

    /**
     * Инициализирует новый исходящий звонок в Стандартном режиме пользователя
     * возвращает ID сессии звонка
     *
     * @param string $leadPhone
     * @param string $callerId
     * @param int    $leadId
     * @param int    $userId
     * @param string $voxUserName
     *
     * @return int
     */
    public function defaultOutgoingCall(
        string      $leadPhone,
        SipEndpoint $sipEndpoint,
        int         $leadId,
        int         $userId,
        string      $voxUserName,
        string      $callerIdForTransferPhone
    ) : int
    {
        $callSessionId = 0;

        $voxAppName = IO::readEnv('CONF_VOX_APP_NAME');
        $voxOutgoingRuleId = (int) IO::readEnv('CONF_VOX_OUTGOING_RULE_ID');

        if (empty($leadPhone) || !$leadId || !$userId || empty($voxUserName) || empty($voxAppName) || !$voxOutgoingRuleId || empty($callerIdForTransferPhone)) {
            return $callSessionId;
        }

        $customData = array_merge(
            $this->getStaticInputData(false),
            [
                'lead_phone' => $leadPhone,
                'sip_endpoint' => [
                    'type' => $sipEndpoint->connectionType,
                    'params' => $sipEndpoint->params,
                ],
                'lead_id' => $leadId,
                'user_id' => $userId,
                'vox_user_name' => $voxUserName,
                'display_name' => 'Lead #' . $leadId,
                'count' => 1,
                'caller_id_for_transfer_phone' => $callerIdForTransferPhone,
            ]
        );

        $res = $this->startScenarioCall([
            'application_name' => $voxAppName, 'rule_id' => $voxOutgoingRuleId, 'script_custom_data' => $customData,
        ]);

        if ($res->result && $res->call_session_history_id) {
            $callSessionId = $res->call_session_history_id;
        }

        return $callSessionId;
    }

    /**
     * Выполняет проверку готовности пользователя принимать вызовы
     * на основе ACD статуса в VoxImplant
     *
     * @param string $voxUserName
     *
     * @return bool
     * @todo перенести в репозиторий кэш
     */
    public function userIsReadyForCall(string $voxUserName) : bool
    {
        $isReadyForCall = false;

        $cacheHit = md5('getUsers');

        if ($cacheResult = Cache::get($cacheHit)) {
            $usersList = $cacheResult['usersList'];
        } else {
            $usersList = $this->getUsers();

            Cache::set($cacheHit, ['usersList' => $usersList], 30);
        }

        foreach ($usersList as $userItem) {
            if (($userItem['user_name'] !== $voxUserName) || ($userItem['acd_status'] !== 'READY')) {
                continue;
            }

            $isReadyForCall = true;
            break;
        }

        $payload = compact('voxUserName', 'isReadyForCall');

        EventManager::dispatch(Events::AFTER_USER_IS_READY_FOR_CALL_VOX_CHECK, $payload);

        return $payload['isReadyForCall'];
    }

    /**
     * Возвращает список пользователей из VoxImplant
     *
     * @return array
     */
    protected function getUsers() : array
    {
        $voxAppName = IO::readEnv('CONF_VOX_APP_NAME');

        $params = $this->setGetUsersParams([
            'application_name' => $voxAppName,
        ]);

        $result = $this->voxApi->Users->GetUsers($params);

        return $result->result;
    }

    /**
     * Устанавливает параметры для запроса списка пользователей из VoxImplant
     *
     * @param array $params
     *
     * @return GetUsersParams
     */
    protected function setGetUsersParams(array $params = []) : GetUsersParams
    {
        $getUsersParams = new GetUsersParams();

        if (!empty($params)) {
            foreach ($params as $paramKey => $paramValue) {
                $getUsersParams->$paramKey = $paramValue;
            }
        }

        return $getUsersParams;
    }

    /**
     * Экспортируует из уведомления о записи разговора полезные данные для saveCallRecord
     *
     * @param $data
     *
     * @return array
     */
    public function exportCallRecordData(array $data) : array
    {
        $notificationTime = $data['notification_time'] / 1000;
        $parseFormat = (is_float($notificationTime)) ? 'U.u' : 'U';
        $notificationTimeObj = DateTime::createFromFormat($parseFormat, $notificationTime);

        $notificationTimeStr = $notificationTimeObj->format('Y-m-d H:i:s.u');

        return [
            'callSessionId' => intval($data['event']['session_id']),
            'callDuration' => (int) ($data['event']['duration']),
            'recordLink' => $data['event']['url'],
            'notificationTimeStr' => $notificationTimeStr,
            'leadId' => intval($data['source']['lead_id'] ?? 0),
            'userId' => intval($data['source']['user_id'] ?? 0),
            'isTransfer' => $data['event']['is_transferred'] ?? false,
        ];
    }

    /**
     * Экспортируует из уведомления данные, полезные для finishCallHook
     *
     * @param array $data
     *
     * @return array
     */
    public function exportCallFinishData(array $data) : array
    {
        if (!empty($data['event']['operator_was_connected']) && !empty($data['event']['connected_operator'])) {
            $fakeEmployeeId = $data['event']['connected_operator'];
        } elseif (!empty($data['source']['vox_user_name'])) {
            $fakeEmployeeId = $data['source']['vox_user_name'];
        } else {
            $fakeEmployeeId = '';
        }

        return [
            'leadId' => intval($data['source']['lead_id']),
            'callSessionId' => intval($data['event']['session_id']),
            'employeeId' => $fakeEmployeeId,
            'connectedOperator' => $data['event']['connected_operator'] ?? 0,
            'lastTalkedEmployeeId' => (!empty($data['event']['operator_was_connected']) && !empty($data['event']['client_was_connected']) && !empty($data['event']['connected_operator'])) ? $data['event']['connected_operator'] : '',
            'isTransfer' => $data['event']['is_transferred'] ?? false,
            'totalTimeDuration' => (int) ($data['event']['total_time_duration']),
            'waitTimeDuration' => (int) ($data['event']['wait_time_duration']),
            'talkTimeDuration' => (int) ($data['event']['talk_time_duration']),
            'direction' => $data['event']['direction'],
            'isLost' => (empty($data['event']['client_was_connected']) || (empty($data['event']['operator_was_connected']) && empty($data['event']['ai_was_connected']))),
            'callSource' => $data['event']['call_source'],
            'voiceMailIsDetected' => (int) ($data['event']['voice_mail_is_detected']),
            'voiceMailDetectionPercent' => (int) ($data['event']['voice_mail_detection_percent']), // From 0 to 100
            'finishReason' => $data['event']['finish_reason'] ?? '',
            'finishCallInitiator' => $data['event']['finish_initiator'], // Possible values: client, operator, system, может также быть пустотая строка, в случае, если я на стороне вокса не смог ничего понять :)
        ];
    }

    /**
     * Экспортируует из уведомления данные, полезные для legIsConnected
     *
     * @param array $data
     *
     * @return array
     */
    public function exportLegIsConnectedData(array $data) : array
    {
        return [
            'callSessionId' => intval($data['event']['session_id']),
            'isOperator' => intval($data['event']['is_operator']),
            'isTransfer' => $data['event']['is_transferred'] ?? false,
            'isAi' => $data['event']['is_ai'] ?? false,
            'employeeId' => 1,
            'legId' => intval($data['event']['leg_id'])
        ];
    }

    /**
     * Экспортируует из уведомления данные, полезные для predictiveAiEvents
     *
     * @param array $data
     *
     * @return array
     */
    public function exportAiEventData(array $data) : array
    {
        return [
            'callSessionId' => intval($data['event']['session_id']),
            'eventCode' => $data['event']['event_code'] ?? '',
        ];
    }

    /**
     * Экспортирует из уведомления VoxImplant данные, полезные для legIsDisconnected
     *
     * @param array $data
     *
     * @return array
     */
    public function exportLegIsDisconnectedData(array $data) : array
    {
        return [
            'leadId' => intval($data['event']['leadId'] ?? 0),
            'employeeId' => 1,
            'callSessionId' => intval($data['event']['session_id'] ?? 0),
            'legId' => intval($data['event']['leg_id'] ?? 0),
            'isFailed' => $data['event']['is_failed'] ?? false,
            'isTransfer' => $data['event']['is_transferred'] ?? false,
            'isOperator' => $data['event']['is_operator'] ?? false,
            'isAi' => $data['event']['is_ai'] ?? false,
            'direction' => $data['event']['direction'],
            'isIncomingCall' => $data['event']['is_incoming_call'] ?? false,
            'callSource' => $data['event']['call_source'],
            'finishReason' => $data['event']['finish_reason'] ?? '',
            'voiceMailIsDetected' => (int) ($data['event']['voice_mail_is_detected'] ?? 0),
            'voiceMailDetectionPercent' => (int) ($data['event']['voice_mail_detection_percent'] ?? 0), // From 0 to 100
            'waitTimeDuration' => (int) ($data['event']['wait_time_duration'] ?? 0),
            'talkTimeDuration' => (int) ($data['event']['talk_time_duration'] ?? 0),
            'totalTimeDuration' => (int) ($data['event']['total_time_duration'] ?? 0),
        ];
    }

    /**
     * Экспортирует из уведомления от VoxImplant данные о входящем звонке,
     * необходимые для работы основного маршрутизатора
     *
     * @param array $data
     *
     * @return array
     */
    public function exportIncomingCallData(array $data) : array
    {
        return [
            'callSessionId' => intval($data['event']['call_session_id']),
            'callStartTs' => intval($data['event']['start_time']),
            'clearPhone' => $data['event']['numa'],
            'dialedPhone' => $data['event']['numb'],
            'clientLegId' => $data['event']['client_leg_id'],
            'sipEndpointType' => $data['event']['sip_endpoint_type'],
            'sipId' => $data['event']['sip_id']
        ];
    }

    /**
     * Экспортирует из уведомления от VoxImplant данные о предиктивном звонке,
     * необходимые для работы основного маршрутизатора
     *
     * @param array $data
     *
     * @return array
     */
    public function exportPredictiveCallData(array $data) : array
    {
        return [
            'callSessionId' => intval($data['event']['call_session_id']), 'callStartTs' => intval($data['event']['start_time']), 'clearPhone' => $data['event']['numb'],
        ];
    }

//    public function createSipRegistration(int $ruleId, bool $isPersistent, string $sipUsername, string $proxy, string $authUser, string $password, string $outboundProxy)
//    {
//        die('Покупка sip');
//
//        $params = new CreateSipRegistrationParams();
//
//        $params->sip_username = $sipUsername;
//        $params->proxy = $proxy;
//        $params->auth_user = $authUser;
//        $params->outbound_proxy = $outboundProxy;
//        $params->password = $password;
//        $params->is_persistent = $isPersistent;
//        $params->rule_id = $ruleId;
//
//        // Create SIP registration.
//        $result = $this->voxApi->SIPRegistration->CreateSipRegistration($params);
//
//        $isFatal = is_null($result->result) || !empty($result->error);
//
//        SystemLogger::write(
//            [
//                'result' => $result,
//                'params' => compact('ruleId', 'isPersistent', 'sipUsername', 'proxy', 'authUser', 'outbound_proxy'),
//            ],
//            $isFatal ? SystemLogger::FATAL: SystemLogger::INFO,
//            ['VoxProvider', 'CreateSipRegistration']
//        );
//
//        if($isFatal){
//            throw new VoxException('Problem when creating SIP registration for VoxImplant telephony!');
//        }
//
//        return $result->result;
//    }

//    public function updateSipRegistration(string $sipId, int $ruleId, string $sipUsername, string $proxy, string $authUser, string $password, string $outboundProxy)
//    {
//        die('Редактирование sip линии');
//
//        $params = new UpdateSipRegistrationParams();
//
//        $params->sip_registration_id = $sipId;
//        $params->sip_username = $sipUsername;
//        $params->proxy = $proxy;
//        $params->auth_user = $authUser;
//        $params->outbound_proxy = $outboundProxy;
//        $params->password = $password;
//        $params->rule_id = $ruleId;
//
//        $result = $this->voxApi->SIPRegistration->UpdateSipRegistration($params);
//
//        $isFatal = is_null($result->result) || !empty($result->error);
//
//        SystemLogger::write(
//            [
//                'result' => $result,
//                'params' => compact('sipId', 'ruleId', 'sipUsername', 'proxy', 'authUser', 'outbound_proxy'),
//            ],
//            $isFatal ? SystemLogger::FATAL: SystemLogger::INFO,
//            ['VoxProvider', 'UpdateSipRegistration']
//        );
//
//        if($isFatal){
//            throw new VoxException('Problem when updating SIP registration for VoxImplant telephony!');
//        }
//
//        return $result->result;
//    }

//    public function deleteSipRegistration(string $sipId)
//    {
//        die('Удаление sip');
//
//        $params = new DeleteSipRegistrationParams();
//
//        $params->cmd = 'DeleteSipRegistration';
//        $params->sip_registration_id = $sipId;
//
//        $result = $this->voxApi->SIPRegistration->DeleteSipRegistration($params);
//
//        $isFatal = is_null($result->result) || !empty($result->error);
//
//        SystemLogger::write(
//            [
//                'result' => $result,
//                'params' => compact('sipId')
//            ],
//            $isFatal ? SystemLogger::FATAL: SystemLogger::INFO,
//            ['VoxProvider', 'DeleteSipRegistration']
//        );
//
//        if($isFatal){
//            throw new VoxException('Problem when deleting SIP registration for VoxImplant telephony!');
//        }
//
//        return $result->result;
//    }

    //@todo покупку номеров пока убираем
//    public function getPhoneNumberCategories(): array
//    {
//        $params = new GetPhoneNumberCategoriesParams();
//
//        $params->locale = $this->locale;
//
//        $result = $this->voxApi->PhoneNumbers->GetPhoneNumberCategories($params);
//
//        if(is_null($result->result) || !empty($result->error)){
//
//            SystemLogger::write(['result' => $result], SystemLogger::FATAL, ['VoxProvider', 'getPhoneNumberCategories']);
//
//            throw new VoxException('The problem with loading VoxImplant telephony categories!');
//        }
//
//        return $result->result;
//    }
//
//    public function getPhoneNumberRegions(string $countryCode, string $phoneCategoryName): array
//    {
//        $params = new GetPhoneNumberRegionsParams();
//
//        $params->country_code = $countryCode;
//        $params->phone_category_name = $phoneCategoryName;
//        $params->locale = $this->locale;
//
//        // Get the Russian regions of the phone numbers.
//        $result = $this->voxApi->PhoneNumbers->GetPhoneNumberRegions($params);
//
//        if(is_null($result->result) || !empty($result->error)){
//
//            SystemLogger::write(['result' => $result], SystemLogger::FATAL, ['VoxProvider', 'GetPhoneNumberRegions']);
//
//            throw new VoxException('The problem with loading VoxImplant telephony regions!');
//        }
//
//        return $result->result;
//    }
//
//    public function getNewPhoneNumbers(string $countryCode, string $phoneCategoryName, int $phoneRegionId, int $count = 2): array
//    {
//        $params = new GetNewPhoneNumbersParams();
//
//        $params->country_code = $countryCode;
//        $params->phone_category_name = $phoneCategoryName;
//        $params->phone_region_id = $phoneRegionId;
//        $params->count = $count;
//        // Get the Russian regions of the phone numbers.
//        $result = $this->voxApi->PhoneNumbers->GetNewPhoneNumbers($params);
//
//        if(is_null($result->result) || !empty($result->error)){
//
//            SystemLogger::write(['result' => $result], SystemLogger::FATAL, ['VoxProvider', 'GetNewPhoneNumbers']);
//
//            throw new VoxException('The problem with loading VoxImplant telephony phones!');
//        }
//
//        return $result->result;
//    }

//    public function isAccountPhoneNumber(string $phone): bool
//    {
//        $params = new IsAccountPhoneNumberParams();
//
//        $params->phone_number = $phone;
//
//        // Check if the phone number belongs to the account.
//        $result = $this->voxApi->PhoneNumbers->IsAccountPhoneNumber($params);
//
//        if(is_null($result->result) || !empty($result->error)){
//
//            SystemLogger::write(['result' => $result], SystemLogger::FATAL, ['VoxProvider', 'IsAccountPhoneNumber']);
//
//            throw new VoxException('The problem in VoxImplant telephony when checking the active phone!');
//        }
//
//        return $result->result;
//    }
}