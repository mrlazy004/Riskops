from app import create_app
app = create_app()
with app.app_context():
    from flask_jwt_extended import create_access_token, decode_token
    token = create_access_token(identity=1)
    print('TOKEN CREATED:', token[:50])
    try:
        decoded = decode_token(token)
        print('DECODED OK:', decoded)
    except Exception as e:
        print('DECODE ERROR:', e)