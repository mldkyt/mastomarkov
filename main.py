import asyncio
import datetime
import os
import re
import typing
from os import getenv

import bs4
import markovify
from bs4 import BeautifulSoup
from mastodon import Mastodon
from sqlalchemy import select, insert, update

from database import last_scan_table, engine, posts_table
from logger import get_logger
from dotenv import load_dotenv

mastodon = Mastodon(access_token="data/pytooter_usercred.secret")
me = mastodon.me()

mastomarkov_logger = get_logger("mastomarkov")

def sanitize_formatting(text: str) -> str:
    result = []
    i = 0
    n = len(text)

    open_tags = []
    open_parentheses = 0
    processed_closing_tags = []

    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else None
        if c == "$" and nxt == "[":
            open_tags.append("$[")
            result.append("$[")
            i += 2
            continue
        if c == "<" and nxt == "i":
            if i + 2 < n and text[i + 2] == ">":
                open_tags.append("<i>")
                result.append("<i>")
                i += 3
            else:
                result.append("<")
                result.append("i")
                i += 2
            continue
        if c == "<" and nxt == "s":
            temp = ["<"]
            j = i + 1
            is_small_tag = False
            while j < n:
                temp.append(text[j])
                if "".join(temp) == "<small>":
                    open_tags.append("<small>")
                    is_small_tag = True
                    j += 1
                    break
                if text[j] == ">" or len(temp) >= 7:
                    j += 1
                    break
                j += 1
            if is_small_tag:
                result.append("<small>")
            else:
                result.append("".join(temp))
            i = j
            continue
        if c == "*" and nxt == "*":
            if "**" not in open_tags:
                open_tags.append("**")
            else:
                try:
                    open_tags.remove("**")
                except ValueError:
                    pass
                processed_closing_tags.append("**")
            result.append("**")
            i += 2
            continue
        if c == "(":
            open_parentheses += 1
            result.append("(")
            i += 1
            continue
        if c == ")":
            if open_parentheses > 0:
                open_parentheses -= 1
            result.append(")")
            i += 1
            continue
        if c == "]":
            if "$[" in open_tags:
                try:
                    open_tags.remove("$[")
                except ValueError:
                    pass
                processed_closing_tags.append("$[")
            result.append("]")
            i += 1
            continue
        if c == "<" and nxt == "/":
            temp = ["<", "/"]
            j = i + 2
            closing_tag_type = ""
            while j < n:
                temp.append(text[j])
                s = "".join(temp)
                if s == "</i>":
                    closing_tag_type = "<i>"
                    j += 1
                    break
                if s == "</small>":
                    closing_tag_type = "<small>"
                    j += 1
                    break
                if text[j] == ">" or len(temp) >= 8:
                    j += 1
                    break
                j += 1
            if closing_tag_type and closing_tag_type in open_tags:
                try:
                    open_tags.remove(closing_tag_type)
                except ValueError:
                    pass
                processed_closing_tags.append(closing_tag_type)
            result.append("".join(temp))
            i = j
            continue
        result.append(c)
        i += 1
    for tag in reversed(open_tags):
        if tag == "$[":
            result.append("]")
        elif tag == "<i>":
            result.append("</i>")
        elif tag == "<small>":
            result.append("</small>")
        elif tag == "**":
            result.append("**")
    if open_parentheses > 0:
        result.append(")" * open_parentheses)

    return "".join(result)

# borrowed from https://stackoverflow.com/questions/30337528/make-beautifulsoup-handle-line-breaks-as-a-browser-would
def get_text(tag: bs4.Tag) -> str:
    _inline_elements = {"a","span","em","strong","u","i","font","mark","label",
                        "s","sub","sup","tt","bdo","button","cite","del","b","a","font",}

    def _get_text(tag: bs4.Tag) -> typing.Generator:
        for child in tag.children:
            if isinstance(child, bs4.Tag):
                # if the tag is a block type tag then yield new lines before after
                is_block_element = child.name not in _inline_elements
                if is_block_element:
                    yield "\n"
                yield from ["\n"] if child.name == "br" else _get_text(child)
                if is_block_element:
                    yield "\n"
            elif isinstance(child, bs4.NavigableString):
                yield child.string

    return "".join(_get_text(tag))

async def get_posts():
    le_target_env = os.getenv("TARGET", "")
    le_target = mastodon.account_search(le_target_env)
    if len(le_target) == 0:
        raise ValueError(f"Account with name {le_target_env} not found")
    le_target = le_target[0]

    while True:
        with engine.begin() as c:
            try:
                # Full check date check
                a = c.execute(
                    select(last_scan_table.c.last_scan).where((last_scan_table.c.id == le_target.id))).fetchone()
                if a is None:
                    c.execute(insert(last_scan_table).values(id=le_target.id, last_scan=datetime.datetime.now()))

                    do_full_scan = False
                else:
                    if (datetime.datetime.now() - a[0]).total_seconds() > 1209600:
                        do_full_scan = True
                        c.execute(update(last_scan_table).where((last_scan_table.c.id == le_target.id)).values(
                            last_scan=datetime.datetime.now()))

                        mastomarkov_logger.info("Full-scan performing on us")
                    else:
                        do_full_scan = False

                # Start fetching notes
                for j in mastodon.pagination_iterator(mastodon.account_statuses(le_target)):
                    # Skip if we hit enough notes and no full scan is being performed
                    a = c.execute(select(posts_table.c.id).where((posts_table.c.id == str(j.id)))).fetchone()
                    if a is not None:
                        if do_full_scan:
                            continue
                        else:
                            break

                    if j.visibility != "public" and j.visibility != "unlisted":
                        continue

                    text = get_text(BeautifulSoup(j.content))

                    c.execute(
                        insert(posts_table).values(
                            id=str(j.id),
                            text=text,
                            has_cw=False,
                            visibility=j.visibility,
                            author=le_target.acct,
                        )
                    )
            except Exception:
                mastomarkov_logger.exception("Failed to query posts for %s", le_target.acct)

        await asyncio.sleep(86400)

async def generate_markov():
    SANITIZE_MENTIONS = getenv("SANITIZE_MENTIONS", "1") == "1"
    SANITIZE_HASHTAGS = getenv("SANITIZE_HASHTAGS", "1") == "1"
    SANITIZE_FORMATTING = getenv("SANITIZE_FORMATTING", "1") == "1"

    REMOVE_MENTIONS = getenv("REMOVE_MENTIONS", "0") == "1"
    REMOVE_HASHTAGS = getenv("REMOVE_HASHTAGS", "0") == "1"
    DEBUG = getenv("DEBUG", "0") == "1"

    while True:
        try:
            posts = []

            with engine.begin() as c:
                a = c.execute(
                    select(
                        posts_table.c.text,
                        posts_table.c.has_cw,
                        posts_table.c.visibility,
                        posts_table.c.author,
                    )
                ).all()

                for i in a:
                    posts.append(i[0])

            if len(posts) == 0:
                print("No posts")
                await asyncio.sleep(10) # wait 10 seconds and try again
                continue

            posts = "\n".join(posts)

            markov = markovify.NewlineText(posts)
            markov.compile(inplace=True)

            output = None
            while output is None:
                output = markov.make_sentence()

            if SANITIZE_FORMATTING:
                output = sanitize_formatting(output)

            if SANITIZE_MENTIONS:
                output = re.sub(r"@(\S)", r"@ \1", output)
            elif REMOVE_MENTIONS:
                output = re.sub(r"@[a-zA-Z.\-_]+", "", output)

            if SANITIZE_HASHTAGS:
                output = re.sub(r"#(\S)", r"# \1", output)
            elif REMOVE_HASHTAGS:
                output = re.sub(r"#\w+", "", output)

            if DEBUG:
                print(output)
            else:
                mastodon.toot(output)
        except Exception:
            mastomarkov_logger.exception("Error occurred:")

        await asyncio.sleep(3600)

def check_env(*items: str):
    for i in items:
        if os.getenv(i) is None or len(os.getenv(i).strip()) == 0:
            print(f"{i} is UNSET!!")
            exit(1)

async def main():
    print("Hello from mastomarkov!")

    load_dotenv()

    check_env("TARGET")

    # start tasks
    tasks = [asyncio.create_task(get_posts()), asyncio.create_task(generate_markov())]

    print("Starting tasks")

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())

