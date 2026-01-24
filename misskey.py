from time import sleep
from typing import Any

from requests import post


class Misskey:
    def __init__(self) -> None:

        self.logged_in = False

        self.instance = ""
        self.token = ""

        self.me = {}

    def log_in(self, instance: str, token: str):
        self.instance: str = instance
        self.token: str = token
        print("[Misskey] API authorizing against", instance)

        me_api = post(f"{instance}/api/i", headers={"Authorization": f"Bearer {token}"}, json={}, )

        self.me: dict = me_api.json()

        if not me_api.ok:
            raise Exception(f"[Misskey] Failed to authorize against {instance}")

        print("[Misskey] Logged in")

        self.logged_in = True


    def get_followers(self):
        if not self.logged_in:
            print("[Misskey] API Call without logged in")
            return

        a = post(f"{self.instance}/api/users/followers", json={"limit": 100, "userId": self.me["id"]},
            headers={"Authorization": f"Bearer {self.token}"}, )
        if not a.ok:
            return

        a = a.json()

        if len(a) == 0:
            return

        last_follow_id = "missingno"

        for i in a:
            last_follow_id = i["followerId"]
            yield i["follower"]

        while True:
            sleep(0.5)

            next_followers = post(f"{self.instance}/api/users/followers",
                json={"limit": 100, "userId": self.me["id"], "untilId": last_follow_id},
                headers={"Authorization": f"Bearer {self.token}"}, )

            if not next_followers.ok:
                break

            next_followers = next_followers.json()
            if len(next_followers) == 0:
                break

            for i in next_followers:
                last_follow_id = i["followerId"]
                yield i["follower"]

    def get_user(self, user_id: str) -> dict | None:
        if not self.logged_in:
            print("[Misskey] API Call without logged in")
            return None

        # Try fetch
        user_api = post(f"{self.instance}/api/users/show", json={"userId": user_id},
            headers={"Authorization": f"Bearer {self.token}"}, )

        if not user_api.ok:
            return None

        user = user_api.json()
        return user

    def follow(self, user_id: str) -> bool:
        if not self.logged_in:
            print("[Misskey] API Call without logged in")
            return False

        user = self.get_user(user_id)
        if user is None:
            return False

        # Already following check

        user = self.get_user(user_id)

        if user["isFollowed"] and user["isFollowing"]:
            return True

        if user["isBlocking"]:
            return False

        # Follow
        req = post(f"{self.instance}/api/following/create", headers={"Authorization": f"Bearer {self.token}"},
            json={"userId": user_id}, )

        if req.status_code == 429:
            # Try again after a delay
            sleep(5)
            req = post(f"{self.instance}/api/following/create",
                headers={"Authorization": f"Bearer {self.token}"}, json={"userId": user_id}, )

        return req.ok

    def unfollow(self, user_id: str) -> bool:
        if not self.logged_in:
            print("[Misskey] API Call without logged in")
            return False

        req = post(f"{self.instance}/api/following/delete", headers={"Authorization": f"Bearer {self.token}"},
            json={"userId": user_id}, )

        if req.status_code == 429:
            sleep(5)
            req = post(f"{self.instance}/api/following/delete",
                headers={"Authorization": f"Bearer {self.token}"}, json={"userId": user_id}, )

        return req.ok

    def post(self, text: str, cw: str | None = None, reply_id: str | None = None, quote_id: str | None = None,
            direct_id: str | None = None, ) -> bool:
        if not self.logged_in:
            print("[Misskey] API Call without logged in")
            return False

        body: dict[str, Any] = {"text": text, "visibility": "public"}

        if reply_id is not None:
            body["replyId"] = reply_id

        if direct_id is not None:
            body["visibility"] = "specified"
            body["visibleUserIds"] = [direct_id]

        if quote_id is not None:
            body["renoteId"] = quote_id

        if cw is not None:
            body["cw"] = cw

        req = post(f"{self.instance}/api/notes/create", headers={"Authorization": f"Bearer {self.token}"},
            json=body, )

        return req.ok

    def get_relationships(self, user_id: str):
        if not self.logged_in:
            print("[Misskey] API Call without logged in")
            return None

        req = post(f"{self.instance}/api/users/relation", headers={"Authorization": f"Bearer {self.token}"},
            json={"userId": user_id}, )

        print(req)

        if not req.ok:
            return None

        return req.json()

    def get_effective_name(self, i: dict | str):
        if not self.logged_in:
            print("[Misskey] API Call without logged in")
            return ""

        if isinstance(i, str):
            user = self.get_user(i)
            if user is None:
                raise Exception(f"[Misskey] Invalid user {i}")
        else:
            user = i

        if user["host"] is None:
            return user["username"]
        return f"{user['username']}@{user['host']}"

    def notifications(self):
        if not self.logged_in:
            print("[Misskey] API Call without logged in")
            return []

        req = post(f"{self.instance}/api/i/notifications", headers={"Authorization": f"Bearer {self.token}", },
            json={"limit": 10, "markAsRead": False, "includeTypes": ["reply", "mention"], }, )

        if not req.ok:
            return []

        return req.json()

    def get_notes(self, user_id: str, limit_100 = False):
        if not self.logged_in:
            print("[Misskey] API Call without logged in")
            return

        first_fetch_notes = post(f"{self.instance}/api/users/notes",
            json={"limit": 100, "userId": user_id, "withRenotes": False, "withQuotes": True, "withReplies": True, },
            headers={"Authorization": f"Bearer {self.token}"}, )
        if not first_fetch_notes.ok:
            return

        first_fetch_notes = first_fetch_notes.json()

        if len(first_fetch_notes) == 0:
            return


        last_note = ""

        for i in first_fetch_notes:
            last_note = i["id"]
            if i["text"] is None:
                continue
            if i["cw"] is None:
                i["cw"] = ""
            yield i

        if limit_100:
            return

        while True:
            sleep(0.5)

            next_notes = post(f"{self.instance}/api/users/notes",
                json={"limit": 100, "userId": user_id, "untilId": last_note, "withRenotes": False, "withQuotes": True,
                    "withReplies": True, }, headers={"Authorization": f"Bearer {self.token}"}, )

            if not next_notes.ok:
                return

            next_notes = next_notes.json()
            if len(next_notes) == 0:
                return

            for i in next_notes:
                last_note = i["id"]
                if i["text"] is None:
                    continue
                if i["cw"] is None:
                    i["cw"] = ""
                yield i
