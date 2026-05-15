
import os

from mastodon import Mastodon

app_name = input("app name [mastomarkov]: ")
if len(app_name.strip()) == 0:
    app_name = "mastomarkov"

instance_url = input("instance url: ")

if not os.path.exists("data"):
    os.mkdir("data")

if not os.path.exists("data/pytooter_clientcred.secret"):
    Mastodon.create_app(
        app_name,
        api_base_url=instance_url,
        to_file='data/pytooter_clientcred.secret'
    )

if os.path.exists("data/pytooter_usercred.secret"):
    print("this user is already authorized, please delete data/pytooter_usercred.secret to reauthorize")
    exit(0)

mode = input("mode [userpass, code] ")

if mode == "userpass":
    username = input("username: ")
    password = input("password: ")

    mastodon = Mastodon(client_id='data/pytooter_clientcred.secret', api_base_url=instance_url)

    mastodon.log_in(
        username,
        password,
        to_file="data/pytooter_usercred.secret"
    )

    print("authorized")
    me = mastodon.me()
    print(f"welcome, {me.acct}")
elif mode == "code":
    mastodon = Mastodon(client_id='data/pytooter_clientcred.secret', api_base_url=instance_url)
    print("Authorize using this url:")
    print(mastodon.auth_request_url())
    code = input("code: ")

    mastodon.log_in(
        code=code,
        to_file="data/pytooter_usercred.secret"
    )

    print("authorized")
    me = mastodon.me()
    print(f"welcome, {me.acct}")
