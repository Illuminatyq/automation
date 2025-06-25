require('dotenv').config();
const fs = require('fs').promises;
const path = require('path');

class ConfigLoader {
    constructor(configPath = 'config/config.json') {
        this.configPath = configPath;
        this.config = null;
    }

    async loadConfig() {
        try {
            const configContent = await fs.readFile(this.configPath, 'utf8');
            this.config = JSON.parse(configContent);
            this._processEnvVariables(this.config);
            return this.config;
        } catch (error) {
            console.error('Error loading config:', error);
            throw error;
        }
    }

    _processEnvVariables(config) {
        for (const key in config) {
            if (typeof config[key] === 'object' && config[key] !== null) {
                this._processEnvVariables(config[key]);
            } else if (typeof config[key] === 'string' && config[key].startsWith('${') && config[key].endsWith('}')) {
                const envVar = config[key].slice(2, -1);
                config[key] = process.env[envVar] || '';
            }
        }
    }

    getEnvironmentConfig(envName = null) {
        if (!this.config) {
            throw new Error('Config not loaded. Call loadConfig() first.');
        }
        envName = envName || this.config.defaultEnvironment;
        return this.config.environments[envName] || {};
    }

    getApiKey(envName = null) {
        const envConfig = this.getEnvironmentConfig(envName);
        return envConfig.api_key || '';
    }

    getBaseUrl(envName = null) {
        const envConfig = this.getEnvironmentConfig(envName);
        return envConfig.baseUrl || '';
    }

    getApiUrl(envName = null) {
        const envConfig = this.getEnvironmentConfig(envName);
        return envConfig.apiUrl || '';
    }
}

// Пример использования:
async function main() {
    const configLoader = new ConfigLoader();
    await configLoader.loadConfig();

    // Получение конфигурации для dev окружения
    const devConfig = configLoader.getEnvironmentConfig('dev');
    console.log('Dev API Key:', devConfig.api_key);

    // Получение конфигурации для SM окружения
    const smConfig = configLoader.getEnvironmentConfig('sm');
    console.log('SM API Key:', smConfig.api_key);
}

// Раскомментируйте для тестирования
// main().catch(console.error);

module.exports = ConfigLoader; 