import os
import glob

def patch_csrf():
    csrf_snippet = """
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <script>
        (function() {
            const csrfToken = "{{ csrf_token() }}";
            const originalFetch = window.fetch;
            window.fetch = function() {
                let [resource, config] = arguments;
                if(config === undefined) {
                    config = {};
                }
                if(config.method && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(config.method.toUpperCase())) {
                    if(config.headers === undefined) {
                        config.headers = {};
                    }
                    config.headers['X-CSRFToken'] = csrfToken;
                }
                return originalFetch(resource, config);
            };
        })();
    </script>
</head>"""

    for filepath in glob.glob('templates/*.html'):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        modified = False

        # Add Token to <head> and override fetch globally
        if '</head>' in content and '<meta name="csrf-token"' not in content:
            content = content.replace('</head>', csrf_snippet)
            modified = True

        # Add Token to plain forms
        if '<form method="POST" action="/login">' in content and 'name="csrf_token"' not in content:
            content = content.replace('<form method="POST" action="/login">', '<form method="POST" action="/login">\n            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>')
            modified = True

        if '<form method="POST" action="/alterar_senha">' in content and 'name="csrf_token"' not in content:
            content = content.replace('<form method="POST" action="/alterar_senha">', '<form method="POST" action="/alterar_senha">\n            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>')
            modified = True

        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Patched CSRF in: {filepath}")

if __name__ == '__main__':
    patch_csrf()
