# pyright: reportMissingImports=false
# SPDX-License-Identifier: GPL-3.0-or-later

# Builds the plugin message (text + TLRPC entities) shared by the inline send
# and the "translate" rebuild, so a translated message is formatted by exactly
# the same code that formats the original.
#
# The rebuild used to go through the SDK's HTML parse mode instead, which lost
# the description formatting; entities are what Telegram actually stores, so
# both paths produce them directly now.

from packutil import logx

try:
    from org.telegram.tgnet import TLRPC
except Exception as e:
    import android_utils as _au; _au.log(f"messageBuilder: import TLRPC failed: {e}")
    TLRPC = None


def u16len(text) -> int:
    # Telegram entity offsets/lengths are UTF-16 code units, not code points:
    # counting with len() drifts as soon as an emoji appears earlier in the
    # message and every following entity lands on the wrong range.
    try:
        from markdown_utils import to_utf16_len
        return to_utf16_len(str(text))
    except Exception:
        return len(str(text).encode("utf-16-le")) // 2


def build_plugin_message(name, version, author, plugin_id, repo_id, description,
                         output_type=None, show_version=True, show_author=True,
                         show_description=True, show_install=True):
    # returns (message_text, entities) — entities sorted by offset, with the
    # description blockquote ahead of the entities it wraps
    entities = []
    parts = []
    offset = 0

    plugin_link = f"tg://packit?plugin={plugin_id}&repo={repo_id}"

    def add(text):
        nonlocal offset
        parts.append(text)
        offset += u16len(text)

    def span(entity, start, text, **attrs):
        entity.offset = start
        entity.length = u16len(text)
        for key, value in attrs.items():
            setattr(entity, key, value)
        entities.append(entity)

    name_text = str(name or "")
    if output_type == "release":
        # "{name} has been released" — name is a bold link, the rest is plain
        span(TLRPC.TL_messageEntityTextUrl(), offset, name_text, url=plugin_link)
        span(TLRPC.TL_messageEntityBold(), offset, name_text)
        add(name_text)
        add(" has been released!")
    elif output_type == "update":
        # "{name} updated to {version}" — name is a bold link, "updated to" bold
        span(TLRPC.TL_messageEntityTextUrl(), offset, name_text, url=plugin_link)
        span(TLRPC.TL_messageEntityBold(), offset, name_text)
        add(name_text)
        updated_text = " updated to "
        span(TLRPC.TL_messageEntityBold(), offset, updated_text)
        add(updated_text)
        add(str(version) if version else "?")
    else:
        # default: "{name} (v{version})"
        span(TLRPC.TL_messageEntityTextUrl(), offset, name_text, url=plugin_link)
        span(TLRPC.TL_messageEntityBold(), offset, name_text)
        add(name_text)
        if show_version and version:
            add(f" (v{version})")

    add("\n")

    if show_author and author:
        add("by ")
        add(str(author))
        add("\n")

    quote_start = offset

    if show_description and description:
        from ...utils.markdown import parse as md_parse
        parsed = md_parse(description)
        if parsed is not None:
            desc_text = parsed.text
            for ent in parsed.entities:
                try:
                    tl_entity = ent.to_tlrpc_object()
                    tl_entity.offset = offset + ent.offset
                    entities.append(tl_entity)
                except Exception as e:
                    logx(f"messageBuilder: entity convert error: {e}", False)
        else:
            desc_text = str(description)

        add(desc_text)
        add("\n")

        quote = TLRPC.TL_messageEntityBlockquote()
        quote.offset = quote_start
        quote.length = offset - quote_start
        entities.append(quote)

    if show_install:
        install_link = f"tg://packit?install&repo={repo_id}&plugin={plugin_id}"
        if version:
            install_link += f"&version={version}"
        install_text = "Install"
        span(TLRPC.TL_messageEntityTextUrl(), offset, install_text, url=install_link)
        add(install_text)
        add(" via ")
        packit_text = "PackIt"
        span(TLRPC.TL_messageEntityTextUrl(), offset, packit_text, url="https://t.me/packitX")
        add(packit_text)

    try:
        entities.sort(key=lambda e: (int(e.offset), -int(e.length)))
    except Exception as e:
        logx(f"messageBuilder: entity sort skipped: {e}", True)

    return "".join(parts), entities


def edit_message_with_entities(message_object, text, entities):
    # SDK edit_message() only accepts entities via its own parse modes, so it
    # cannot carry ours. Drive the host directly instead: the fields it fills
    # are plain MessageObject members read by SendMessagesHelper.editMessage.
    try:
        from java.util import ArrayList
        from client_utils import get_send_messages_helper
        from android_utils import run_on_ui_thread

        java_entities = None
        if entities:
            java_entities = ArrayList()
            for entity in entities:
                java_entities.add(entity)

        message_object.editingMessage = text
        message_object.editingMessageEntities = java_entities

        helper = get_send_messages_helper()

        def _edit():
            try:
                helper.editMessage(message_object, None, None, None, None,
                                   None, None, False, False, None)
            except Exception as e:
                logx(f"messageBuilder: editMessage failed: {e}", False)

        run_on_ui_thread(_edit)
        return True
    except Exception as e:
        logx(f"messageBuilder: edit_message_with_entities error: {e}", False)
        return False
