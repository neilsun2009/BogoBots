available_models = [
    {
        'group': 'OpenAI',
        # 'icon': 'https://openaiapi-site.azureedge.net/public-assets/d/aa8667594c/favicon.png',
        'icon': 'https://openai.com/favicon.ico',
        'supports_official_api': True,
        'official_api_base': 'https://api.openai.com/v1',
        'supports_open_router': True,
        'open_router_prefix': 'openai',
        'models': [
            {
                'display_name': 'GPT-4o',
                'api_name': 'gpt-4o-2024-05-13',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'GPT-4 Turbo 2024-04-09',
                'api_name': 'gpt-4-turbo',
                'is_free': False,
                'native_tool_support': True,
            }
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
                'display_name': 'Llama 3 8B Instruct (free)',
                'api_name': 'llama-3-8b-instruct:free',
                'is_free': True,
                'native_tool_support': False,
            },
            {
                'display_name': 'Llama 3 70B Instruct',
                'api_name': 'llama-3-70b-instruct',
                'is_free': False,
                'native_tool_support': False,
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
                'display_name': 'Gemma 7B Instruct (free)',
                'api_name': 'gemma-7b-it:free',
                'is_free': True,
                'native_tool_support': False,
            },
            {
                'display_name': 'Gemini Flash 1.5',
                'api_name': 'gemini-flash-1.5',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Gemini Pro 1.5',
                'api_name': 'gemini-pro-1.5',
                'is_free': False,
                'native_tool_support': True,
            },
            {
                'display_name': 'Gemini Pro 1.0',
                'api_name': 'gemini-pro',
                'is_free': False,
                'native_tool_support': False,
            },
        ]
    },
]