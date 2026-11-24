import sys, os

print("[TIMONA] Applying proprietary customizations (Option B Chat, Technician Alias, UI)... ")

def patch_connection_rs():
    path = "src/server/connection.rs"
    if not os.path.exists(path):
        print(f"[WARN] {path} does not exist")
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    target = "        if let Some(message::Union::Misc(misc)) = &msg.union {\n            // Move the CloseReason forward"
    replacement = """        if let Some(message::Union::Misc(misc)) = &msg.union {
            // TIMONA Remote: Option B - Pre-Accept Bidirectional Chat
            if let Some(misc::Union::ChatMessage(c)) = &misc.union {
                self.send_to_cm(ipc::Data::ChatMessage { text: c.text.clone() });
                self.chat_unanswered = true;
                self.update_auto_disconnect_timer();
                return true;
            }
            // Move the CloseReason forward"""
    if target in content:
        content = content.replace(target, replacement, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[OK] src/server/connection.rs patched for Pre-Accept Chat")
    else:
        print("[WARN] target not found in src/server/connection.rs")

def patch_client_rs():
    path = "src/client.rs"
    if not os.path.exists(path):
        print(f"[WARN] {path} does not exist")
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    target = "        if display_name.is_empty() {\n            display_name = crate::username();\n        }"
    replacement = """        if display_name.is_empty() {
            let custom_tech = LocalConfig::get_option("custom_technician_name");
            if !custom_tech.is_empty() {
                display_name = custom_tech;
            }
        }
        if display_name.is_empty() {
            display_name = crate::username();
        }"""
    if target in content:
        content = content.replace(target, replacement, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("[OK] src/client.rs patched for Custom Technician Alias")
    else:
        print("[WARN] target not found in src/client.rs")

def patch_server_page_dart():
    path = "flutter/lib/desktop/pages/server_page.dart"
    if not os.path.exists(path):
        print(f"[WARN] {path} does not exist")
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    target1 = "          Offstage(\n            offstage: !client.authorized ||\n                (client.type_() != ClientType.remote"
    replacement1 = "          Offstage(\n            offstage: (client.type_() != ClientType.remote"
    if target1 in content:
        content = content.replace(target1, replacement1, 1)
        print("[OK] server_page.dart chat button unlocked for pre-accept")
    else:
        print("[WARN] target1 not found in server_page.dart")

    target2 = "    WidgetsBinding.instance.addPostFrameCallback((_) {\n      gFFI.serverModel.tabController.onSelected?.call(client.id.toString());\n    });"
    replacement2 = """    WidgetsBinding.instance.addPostFrameCallback((_) {
      gFFI.serverModel.tabController.onSelected?.call(client.id.toString());
      if (!client.authorized) {
        gFFI.chatModel.showChatPage(MessageKey(client.peerId, client.id));
      }
    });"""
    if target2 in content:
        content = content.replace(target2, replacement2, 1)
        print("[OK] server_page.dart pre-accept chat auto-open added")
    else:
        print("[WARN] target2 not found in server_page.dart")

    target3 = "            if (showAccept)\n              Expanded(\n                child: Column(\n                  children: [\n                    buildButton(\n                      context,\n                      color: MyTheme.accent,"
    replacement3 = """            Expanded(
              child: buildButton(
                context,
                color: Color(0xff0071ff),
                onClick: () {
                  gFFI.chatModel.toggleCMChatPage(MessageKey(client.peerId, client.id));
                },
                text: Chat,
                icon: Icon(Icons.chat_bubble_outline, color: Colors.white, size: 14),
                textColor: Colors.white,
              ),
            ),
            if (showAccept)
              Expanded(
                child: Column(
                  children: [
                    buildButton(
                      context,
                      color: MyTheme.accent,"""
    if target3 in content:
        content = content.replace(target3, replacement3, 1)
        print("[OK] server_page.dart pre-accept Chat button added to control panel")
    else:
        print("[WARN] target3 not found in server_page.dart")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    patch_connection_rs()
    patch_client_rs()
    patch_server_page_dart()
    print("[TIMONA] Patches applied successfully.")
