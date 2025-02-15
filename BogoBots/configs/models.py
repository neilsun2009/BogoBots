available_models = [
    {
        'group': 'DeepSeek',
        'icon': 'https://www.deepseek.com/favicon.ico',
        'supports_official_api': False,
        'supports_open_router': True,
        'open_router_prefix': 'deepseek',
        'models': [
            {
                'display_name': 'DeepSeek R1 (free)',
                'api_name': 'deepseek-r1:free',
                'is_free': True,
                'native_tool_support': False,
            },
            {
                'display_name': 'DeepSeek R1',
                'api_name': 'deepseek-r1',
                'is_free': False,
                'native_tool_support': False,
            },
            {
                'display_name': 'DeepSeek V3 (free)',
                'api_name': 'deepseek-chat:free',
                'is_free': True,
                'native_tool_support': False,
            },
            {
                'display_name': 'DeepSeek V3',
                'api_name': 'deepseek-chat',
                'is_free': False,
                'native_tool_support': False,
            },
        ]
    },
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
                'display_name': 'o1',
                'api_name': 'o1',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'o1-mini',
                'api_name': 'openai/o1-mini',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'GPT-4o',
                'api_name': 'gpt-4o-2024-11-20',
                'is_free': False,
                'native_tool_support': True,
            }
        ]
    },
    {
        'group': 'Qwen',
        'icon': 'https://img.alicdn.com/imgextra/i4/O1CN01FOwagl1XBpyVA2QVy_!!6000000002886-2-tps-512-512.png',
        'supports_official_api': True,
        'official_api_base': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'official_api_link': 'https://bailian.console.aliyun.com/',
        'supports_open_router': False,
        'open_router_prefix': 'qwen',
        'models': [
            {
                'display_name': 'Qwen Max',
                'api_name': 'qwen-max',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Qwen Omni Turbo',
                'api_name': 'qwen-omni-turbo',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Qwen2.5 7B Instruct',
                'api_name': 'qwen2.5-7b-instruct-1m',
                'is_free': False,
                'native_tool_support': False,
            },
            {
                'display_name': 'Qwen2.5 72B Instruct',
                'api_name': 'qwen2.5-72b-instruct',
                'is_free': False,
                'native_tool_support': False,
            },
        ]
    },
    {
        'group': 'Meta Llama',
        'icon': 'https://static.xx.fbcdn.net/rsrc.php/y5/r/m4nf26cLQxS.ico',
        'supports_official_api': False,
        'supports_open_router': True,
        'open_router_prefix': 'meta-llama',
        'models': [
            {
                'display_name': 'Llama 3.3 70B Instruct (free)',
                'api_name': 'llama-3.3-70b-instruct:free',
                'is_free': True,
                'native_tool_support': False,
            },
            {
                'display_name': 'Llama 3.2 3B Instruct',
                'api_name': 'llama-3.2-3b-instruct',
                'is_free': False,
                'native_tool_support': False,
            },
        ]
    },
    {
        'group': 'Anthropic',
        'icon': 'https://www.anthropic.com/images/icons/apple-touch-icon.png',
        'supports_official_api': False,
        'supports_open_router': True,
        'open_router_prefix': 'anthropic',
        'models': [
            {
                'display_name': 'Claude 3.5 Sonnet',
                'api_name': 'claude-3.5-sonnet',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Claude 3.5 Haiku',
                'api_name': 'claude-3.5-haiku',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Claude 3 Opus',
                'api_name': 'claude-3-opus',
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
                'display_name': 'Gemini Flash 2.0 Thinking Expr (free)',
                'api_name': 'gemini-2.0-flash-thinking-exp:free',
                'is_free': True,
                'native_tool_support': True,
            },
            {
                'display_name': 'Gemini Flash 2.0',
                'api_name': 'gemini-2.0-flash-001',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Gemini Flash 2.0 Expr (free)',
                'api_name': 'gemini-2.0-flash-exp:free',
                'is_free': True,
                'native_tool_support': True,
            },
            {
                'display_name': 'Gemini Pro 2.0 Expr (free)',
                'api_name': 'gemini-2.0-pro-exp-02-05:free',
                'is_free': True,
                'native_tool_support': True,
            },
            {
                'display_name': 'Gemma 2 9B Instruct (free)',
                'api_name': 'gemma-2-9b-it:free',
                'is_free': True,
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
                'display_name': 'Grok 2 1212',
                'api_name': 'grok-2-1212',
                'is_free': False,
                'native_tool_support': False,
            },
        ]
    },
    {
        'group': 'Microsoft',
        'icon': 'https://c.s-microsoft.com/favicon.ico?v2',
        'supports_official_api': False,
        'supports_open_router': True,
        'open_router_prefix': 'microsoft',
        'models': [
            {
                'display_name': 'Phi 3 Mini 128k Instruct (free)',
                'api_name': 'phi-3-mini-128k-instruct:free',
                'is_free': True,
                'native_tool_support': False,
            },
            {
                'display_name': 'Phi 3 Medium 128k Instruct (free)',
                'api_name': 'phi-3-medium-128k-instruct:free',
                'is_free': True,
                'native_tool_support': False,
            },
        ]
    },
]