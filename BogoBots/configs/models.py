available_models = [
    {
        'group': 'OpenAI',
        'icon': 'https://openai.com/favicon.ico',
        'supports_official_api': True,
        'official_api_base': 'https://api.openai.com/v1',
        'official_api_link': 'https://openai.com/api/',
        'supports_open_router': True,
        'open_router_prefix': 'openai',
        'models': [
            {
                'display_name': 'GPT-5.4 Mini',
                'api_name': 'gpt-5.4-mini',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'GPT-5.4',
                'api_name': 'gpt-5.4',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'GPT-OSS 120B',
                'api_name': 'gpt-oss-120b',
                'is_free': False,
                'native_tool_support': True,
            },
        ]
    },
    {
        'group': 'Qwen',
        'icon': 'https://img.alicdn.com/imgextra/i4/O1CN01FOwagl1XBpyVA2QVy_!!6000000002886-2-tps-512-512.png',
        'supports_official_api': False,
        'official_api_base': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'official_api_link': 'https://bailian.console.aliyun.com/',
        'supports_open_router': True,
        'open_router_prefix': 'qwen',
        'models': [
            {
                'display_name': 'Qwen 3.6 Plus',
                'api_name': 'qwen3.6-plus',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Qwen 3.5 Flash',
                'api_name': 'qwen3.5-flash-02-23',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Qwen 3.5 397B A17B',
                'api_name': 'qwen3.5-397b-a17b',
                'is_free': False,
                'native_tool_support': False,
            },
        ]
    },
    {
        'group': 'DeepSeek',
        'icon': 'https://www.deepseek.com/favicon.ico',
        'supports_official_api': False,
        'supports_open_router': True,
        'open_router_prefix': 'deepseek',
        'models': [
            {
                'display_name': 'DeepSeek V3.2',
                'api_name': 'deepseek-v3.2',
                'is_free': False,
                'native_tool_support': False,
            },
        ]
    },
    # {
    #     'group': 'Meta Llama',
    #     'icon': 'https://static.xx.fbcdn.net/rsrc.php/y5/r/m4nf26cLQxS.ico',
    #     'supports_official_api': False,
    #     'supports_open_router': True,
    #     'open_router_prefix': 'meta-llama',
    #     'models': [
    #         {
    #             'display_name': 'Llama 3.3 70B Instruct (free)',
    #             'api_name': 'llama-3.3-70b-instruct:free',
    #             'is_free': True,
    #             'native_tool_support': False,
    #         },
    #         {
    #             'display_name': 'Llama 3.2 3B Instruct',
    #             'api_name': 'llama-3.2-3b-instruct',
    #             'is_free': False,
    #             'native_tool_support': False,
    #         },
    #     ]
    # },
    {
        'group': 'Anthropic',
        'icon': 'https://www.anthropic.com/images/icons/apple-touch-icon.png',
        'supports_official_api': False,
        'supports_open_router': True,
        'open_router_prefix': 'anthropic',
        'models': [
            {
                'display_name': 'Claude Sonnet 4.6',
                'api_name': 'claude-sonnet-4.6',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Claude Opus 4.6',
                'api_name': 'claude-opus-4.6',
                'is_free': False,
                'native_tool_support': True,
            },
        ]
    },
    {
        'group': 'Google',
        'icon': 'https://www.google.com/images/branding/googleg/1x/googleg_standard_color_128dp.png',
        'supports_official_api': False,
        'supports_open_router': True,
        'open_router_prefix': 'google',
        'models': [
            {
                'display_name': 'Gemini 3.1 Flash Lite Preview',
                'api_name': 'gemini-3.1-flash-lite-preview',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Gemini 3.1 Pro Preview',
                'api_name': 'gemini-3.1-pro-preview',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Gemma 4 26B A4B',
                'api_name': 'gemma-4-26b-a4b-it',
                'is_free': False,
                'native_tool_support': False,
            },
        ]
    },
    {
        'group': 'xAI',
        'icon': 'https://x.ai/favicon.ico',
        'supports_official_api': False,
        'supports_open_router': True,
        'open_router_prefix': 'x-ai',
        'models': [
            {
                'display_name': 'Grok 4.20',
                'api_name': 'grok-4.20',
                'is_free': False,
                'native_tool_support': False,
            },
            {
                'display_name': 'Grok 4.1 Fast',
                'api_name': 'grok-4.1-fast',
                'is_free': False,
                'native_tool_support': False,
            },
        ]
    },
    # {
    #     'group': 'Microsoft',
    #     'icon': 'https://c.s-microsoft.com/favicon.ico?v2',
    #     'supports_official_api': False,
    #     'supports_open_router': True,
    #     'open_router_prefix': 'microsoft',
    #     'models': [
    #         {
    #             'display_name': 'Phi 3 Mini 128k Instruct (free)',
    #             'api_name': 'phi-3-mini-128k-instruct:free',
    #             'is_free': True,
    #             'native_tool_support': False,
    #         },
    #         {
    #             'display_name': 'Phi 3 Medium 128k Instruct (free)',
    #             'api_name': 'phi-3-medium-128k-instruct:free',
    #             'is_free': True,
    #             'native_tool_support': False,
    #         },
    #     ]
    # },
]