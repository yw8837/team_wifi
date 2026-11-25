from test_public_release import public_mode


def test_invalid_login_feedback_is_korean_and_never_echoes_credentials(public_mode):
    client, _, _ = public_mode
    secret = 'do-not-echo-this-private-value' * 5
    response = client.post('/api/auth/login', json={'email': 'private@example.test', 'password': secret})
    assert response.status_code == 422
    assert secret not in response.text and 'private@example.test' not in response.text
    assert '이메일 형식' in response.text and '128자 이내' in response.text
    assert all(set(error) == {'loc', 'msg', 'type'} for error in response.json()['detail'])
