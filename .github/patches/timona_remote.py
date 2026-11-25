import glob
import os
import re

print("[TIMONA] Applying proprietary customizations (Option B Pre-Accept Chat, Technician Alias, OTA Updates, White-Label)...")


def patch_file(path, operations):
    if not os.path.exists(path):
        print(f"[WARN] {path} not found")
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    orig = content
    for op in operations:
        mode = op[0]
        if mode == "exact":
            _, target, replacement, desc = op
            if target in content:
                content = content.replace(target, replacement, 1)
                print(f"[OK] {path}: {desc}")
            elif replacement in content:
                print(f"[SKIP] {path}: already patched ({desc})")
            else:
                print(f"[WARN] {path}: target not found for ({desc})")
        elif mode == "regex":
            _, pattern, repl, desc, flags = op
            new_content, count = re.subn(pattern, repl, content, count=1, flags=flags)
            if count > 0:
                content = new_content
                print(f"[OK] {path}: {desc}")
            else:
                print(f"[WARN] {path}: regex did not match ({desc})")
        elif mode == "regex_optional":
            _, pattern, repl, desc, flags = op
            new_content, count = re.subn(pattern, repl, content, count=0, flags=flags)
            if count > 0:
                content = new_content
                print(f"[OK] {path}: {desc} ({count} occurrences)")
    if content != orig:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    return False


def patch_connection_rs():
    # Option B: Permitir troca de pacotes ChatMessage antes do cliente clicar em Aceitar
    patch_file(
        "src/server/connection.rs",
        [
            (
                "exact",
                "        if let Some(message::Union::Misc(misc)) = &msg.union {\n            // Move the CloseReason forward",
                """        if let Some(message::Union::Misc(misc)) = &msg.union {
            // TIMONA Remote: Option B - Chat bidirecional pre-aceite
            if let Some(misc::Union::ChatMessage(c)) = &misc.union {
                self.send_to_cm(ipc::Data::ChatMessage { text: c.text.clone() });
                self.chat_unanswered = true;
                self.update_auto_disconnect_timer();
                return true;
            }
            // Move the CloseReason forward""",
                "allow ChatMessage before authorization",
            )
        ],
    )


def patch_client_rs():
    # Nome de perfil customizado do tecnico + URL white-label em erro
    patch_file(
        "src/client.rs",
        [
            (
                "exact",
                "        if display_name.is_empty() {\n            display_name = crate::username();\n        }",
                """        if display_name.is_empty() {
            let custom_tech = LocalConfig::get_option("custom_technician_name");
            if !custom_tech.trim().is_empty() {
                display_name = custom_tech.trim().to_owned();
            }
        }
        if display_name.is_empty() {
            display_name = crate::username();
        }""",
                "custom_technician_name display override",
            ),
            (
                "exact",
                'link: "https://rustdesk.com/docs/en/manual/linux/#login-screen",',
                'link: "https://www.supportti.net/",',
                "remove rustdesk.com doc link",
            ),
        ],
    )


def patch_server_page_dart():
    # Janela --cm do usuario remoto: liberar botao de chat, auto-abrir chat no PendingApproval, botao Chat direto
    patch_file(
        "flutter/lib/desktop/pages/server_page.dart",
        [
            (
                "exact",
                "    WidgetsBinding.instance.addPostFrameCallback((_) {\n      gFFI.serverModel.tabController.onSelected?.call(client.id.toString());\n    });",
                """    WidgetsBinding.instance.addPostFrameCallback((_) {
      gFFI.serverModel.tabController.onSelected?.call(client.id.toString());
      if (!client.authorized) {
        gFFI.chatModel.showChatPage(MessageKey(client.peerId, client.id));
      }
    });""",
                "auto-open chat side panel when waiting approval",
            ),
            (
                "exact",
                "          Offstage(\n            offstage: !client.authorized ||\n                (client.type_() != ClientType.remote",
                "          Offstage(\n            offstage: (client.type_() != ClientType.remote",
                "unlock chat button in header before accept",
            ),
            (
                "exact",
                "        Row(\n          mainAxisAlignment: MainAxisAlignment.center,\n          children: [\n            if (showAccept)",
                """        buildButton(
          context,
          color: Color(0xff0071ff),
          onClick: () {
            gFFI.chatModel.toggleCMChatPage(MessageKey(client.peerId, client.id));
          },
          text: 'Chat',
          icon: Icon(Icons.chat_bubble_outline, color: Colors.white, size: 14),
          textColor: Colors.white,
        ),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (showAccept)""",
                "add full-width Chat button to unauthorized control panel",
            ),
        ],
    )


def patch_technician_preaccept_chat():
    # Lado do tecnico: incluir chat ao vivo dentro de showWaitAcceptDialog + inicializar ChatModel
    patch_file(
        "flutter/lib/common/widgets/dialog.dart",
        [
            (
                "exact",
                "import 'address_book.dart';",
                """import 'address_book.dart';
import 'chat_page.dart';
import '../../models/chat_model.dart';""",
                "import ChatPage and ChatModel",
            ),
            (
                "exact",
                """void showWaitAcceptDialog(SessionID sessionId, String type, String title,
    String text, OverlayDialogManager dialogManager) {
  dialogManager.dismissAll();
  dialogManager.show((setState, close, context) {
    onCancel() {
      closeConnection();
    }

    return CustomAlertDialog(
      title: null,
      content: msgboxContent(type, title, text),
      actions: [
        dialogButton('Cancel', onPressed: onCancel, isOutline: true),
      ],
      onCancel: onCancel,
    );
  });
}""",
                """void showWaitAcceptDialog(SessionID sessionId, String type, String title,
    String text, OverlayDialogManager dialogManager,
    {ChatModel? chatModel}) {
  dialogManager.dismissAll();
  dialogManager.show((setState, close, context) {
    onCancel() {
      closeConnection();
    }

    return CustomAlertDialog(
      title: null,
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          msgboxContent(type, title, text),
          if (chatModel != null) ...[
            const SizedBox(height: 12),
            Container(
              width: 380,
              height: 250,
              decoration: BoxDecoration(
                border: Border.all(color: Theme.of(context).dividerColor),
                borderRadius: BorderRadius.circular(8),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: ChatPage(chatModel: chatModel),
              ),
            ),
          ],
        ],
      ),
      actions: [
        dialogButton('Cancel', onPressed: onCancel, isOutline: true),
      ],
      onCancel: onCancel,
    );
  });
}""",
                "embed live ChatPage inside showWaitAcceptDialog",
            ),
        ],
    )

    patch_file(
        "flutter/lib/models/model.dart",
        [
            (
                "exact",
                "    } else if (type == 'wait-remote-accept-nook') {\n      showWaitAcceptDialog(sessionId, type, title, text, dialogManager);",
                """    } else if (type == 'wait-remote-accept-nook') {
      parent.target?.chatModel
          .changeCurrentKey(MessageKey(peerId, ChatModel.clientModeID));
      showWaitAcceptDialog(sessionId, type, title, text, dialogManager,
          chatModel: parent.target?.chatModel);""",
                "initialize client chat key and pass chatModel to wait dialog",
            ),
        ],
    )

    patch_file(
        "flutter/lib/models/chat_model.dart",
        [
            (
                "exact",
                """      if (isConnManager) {
        if (!_isShowCMSidePage) {
          await toggleCMChatPage(key);
        }
      } else {
        if (_isChatOverlayHide()) {
          await toggleChatOverlay();
        }
      }""",
                """      if (isConnManager) {
        if (!_isShowCMSidePage) {
          await toggleCMChatPage(key);
        }
      } else if (parent.target?.ffiModel.pi.isSet.isTrue == true) {
        if (_isChatOverlayHide()) {
          await toggleChatOverlay();
        }
      }""",
                "avoid duplicate overlay while pre-accept wait dialog is showing",
            ),
        ],
    )


def patch_ota_updates():
    # Desbloquear OTA para custom client e apontar para https://installremote.timona.com.br/updates/
    patch_file(
        "src/common.rs",
        [
            (
                "exact",
                """pub fn check_software_update() {
    if is_custom_client() {
        return;
    }
    let opt = LocalConfig::get_option(keys::OPTION_ENABLE_CHECK_UPDATE);
    if config::option2bool(keys::OPTION_ENABLE_CHECK_UPDATE, &opt) {
        std::thread::spawn(move || allow_err!(do_check_software_update()));
    }
}""",
                """pub fn check_software_update() {
    let opt = LocalConfig::get_option(keys::OPTION_ENABLE_CHECK_UPDATE);
    if config::option2bool(keys::OPTION_ENABLE_CHECK_UPDATE, &opt) {
        std::thread::spawn(move || allow_err!(do_check_software_update()));
    }
}""",
                "allow check_software_update in custom client",
            ),
            (
                "exact",
                """#[tokio::main(flavor = "current_thread")]
pub async fn do_check_software_update() -> hbb_common::ResultType<()> {
    let (request, url) =
        hbb_common::version_check_request(hbb_common::VER_TYPE_RUSTDESK_CLIENT.to_string());
    let proxy_conf = Config::get_socks();
    let tls_url = get_url_for_tls(&url, &proxy_conf);
    let tls_type = get_cached_tls_type(tls_url);
    let is_tls_not_cached = tls_type.is_none();
    let tls_type = tls_type.unwrap_or(TlsType::Rustls);
    let client = create_http_client_async(tls_type, false);
    let latest_release_response = match client.post(&url).json(&request).send().await {
        Ok(resp) => {
            upsert_tls_cache(tls_url, tls_type, false);
            resp
        }
        Err(err) => {
            if is_tls_not_cached && err.is_request() {
                let tls_type = TlsType::NativeTls;
                let client = create_http_client_async(tls_type, false);
                let resp = client.post(&url).json(&request).send().await?;
                upsert_tls_cache(tls_url, tls_type, false);
                resp
            } else {
                return Err(err.into());
            }
        }
    };
    let bytes = latest_release_response.bytes().await?;
    let resp: hbb_common::VersionCheckResponse = serde_json::from_slice(&bytes)?;
    let response_url = resp.url;
    let latest_release_version = response_url.rsplit('/').next().unwrap_or_default();""",
                """#[tokio::main(flavor = "current_thread")]
pub async fn do_check_software_update() -> hbb_common::ResultType<()> {
    let url = "https://installremote.timona.com.br/updates/version.json".to_string();
    let proxy_conf = Config::get_socks();
    let tls_url = get_url_for_tls(&url, &proxy_conf);
    let tls_type = get_cached_tls_type(tls_url);
    let is_tls_not_cached = tls_type.is_none();
    let tls_type = tls_type.unwrap_or(TlsType::Rustls);
    let client = create_http_client_async(tls_type, false);
    let latest_release_response = match client.get(&url).send().await {
        Ok(resp) => {
            upsert_tls_cache(tls_url, tls_type, false);
            resp
        }
        Err(err) => {
            if is_tls_not_cached && err.is_request() {
                let tls_type = TlsType::NativeTls;
                let client = create_http_client_async(tls_type, false);
                let resp = client.get(&url).send().await?;
                upsert_tls_cache(tls_url, tls_type, false);
                resp
            } else {
                return Err(err.into());
            }
        }
    };
    let bytes = latest_release_response.bytes().await?;
    let resp: serde_json::Value = serde_json::from_slice(&bytes)?;
    let latest_release_version = resp
        .get("version")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .to_string();
    let response_url = if latest_release_version.is_empty() {
        String::new()
    } else {
        format!("https://installremote.timona.com.br/updates/{}", latest_release_version)
    };""",
                "fetch proprietary version.json for OTA update check",
            ),
        ],
    )

    patch_file(
        "src/flutter_ffi.rs",
        [
            (
                "exact",
                """        } else if key.starts_with("download-file-") {
            let _version = key.replace("download-file-", "");
            #[cfg(target_os = "windows")]
            return match (
                crate::platform::windows::is_msi_installed(),
                crate::common::is_custom_client(),
            ) {
                (Ok(true), false) => match crate::platform::windows::release_arch_suffix() {
                    Some(arch) => format!("rustdesk-{_version}-{arch}.msi"),
                    None => "error:unsupported".to_owned(),
                },
                (Ok(true), true) | (Ok(false), _) => {
                    match crate::platform::windows::release_arch_suffix() {
                        Some(arch) => format!("rustdesk-{_version}-{arch}.exe"),
                        None => "error:unsupported".to_owned(),
                    }
                }
                (Err(e), _) => {
                    log::error!("Failed to check if is msi: {}", e);
                    format!("error:update-failed-check-msi-tip")
                }
            };""",
                """        } else if key.starts_with("download-file-") {
            let _version = key.replace("download-file-", "");
            #[cfg(target_os = "windows")]
            return match crate::platform::windows::is_msi_installed() {
                Ok(true) => "TimonaRemote-latest.msi".to_owned(),
                Ok(false) => "TimonaRemote-latest.exe".to_owned(),
                Err(e) => {
                    log::error!("Failed to check if is msi: {}", e);
                    "error:update-failed-check-msi-tip".to_owned()
                }
            };""",
                "return TimonaRemote-latest exe/msi filename in download-file-",
            ),
        ],
    )

    patch_file(
        "src/updater.rs",
        [
            (
                "exact",
                """    #[cfg(target_os = "windows")]
    let update_msi = crate::platform::is_msi_installed()? && !crate::is_custom_client();""",
                """    #[cfg(target_os = "windows")]
    let update_msi = crate::platform::is_msi_installed()?;""",
                "allow MSI updates in custom client",
            ),
            (
                "exact",
                """        #[cfg(target_os = "windows")]
        let download_url = if cfg!(feature = "flutter") {
            let Some(arch) = crate::platform::windows::release_arch_suffix() else {
                bail!(
                    "Unsupported Windows release architecture: {}",
                    std::env::consts::ARCH
                );
            };
            format!(
                "{}/rustdesk-{}-{}.{}",
                download_url,
                version,
                arch,
                if update_msi { "msi" } else { "exe" }
            )
        } else {
            format!("{}/rustdesk-{}-x86-sciter.exe", download_url, version)
        };""",
                """        #[cfg(target_os = "windows")]
        let download_url = format!(
            "https://installremote.timona.com.br/updates/{}",
            if update_msi {
                "TimonaRemote-latest.msi"
            } else {
                "TimonaRemote-latest.exe"
            }
        );""",
                "point updater download_url to installremote.timona.com.br",
            ),
            # Restore &download_url if earlier generator-windows.yml sed replaced it with literal URL
            (
                "regex_optional",
                r'create_http_client_with_url_strict\("https?://[^"]+"\)',
                r"create_http_client_with_url_strict(&download_url)",
                "use &download_url in create_http_client_with_url_strict",
                0,
            ),
            (
                "regex_optional",
                r'get_download_file_from_url\("https?://[^"]+"\)',
                r"get_download_file_from_url(&download_url)",
                "use &download_url in get_download_file_from_url",
                0,
            ),
            (
                "regex_optional",
                r'client\.head\("https?://[^"]+"\)',
                r"client.head(&download_url)",
                "use &download_url in client.head",
                0,
            ),
            (
                "regex_optional",
                r'client\.get\("https?://[^"]+"\)',
                r"client.get(&download_url)",
                "use &download_url in client.get",
                0,
            ),
            (
                "exact",
                """    if !url.starts_with("https://github.com/")
        || parsed.scheme() != "https"
        || parsed.host_str() != Some("github.com")
        || !parsed.username().is_empty()
        || parsed.password().is_some()
        || parsed.port().is_some()
        || parsed.query().is_some()
        || parsed.fragment().is_some()
    {
        return None;
    }

    let mut segments = parsed.path_segments()?;
    let owner = segments.next()?;
    let repo = segments.next()?;
    let releases = segments.next()?;
    let download = segments.next()?;
    let tag = segments.next()?;
    let filename = segments.next()?;

    if owner != "rustdesk"
        || repo != "rustdesk"
        || releases != "releases"
        || download != "download"
        || tag.is_empty()
        || segments.next().is_some()
        || !is_plain_update_filename(filename)
    {
        return None;
    }

    Some(std::env::temp_dir().join(filename))""",
                """    if parsed.scheme() != "https"
        || !parsed.username().is_empty()
        || parsed.password().is_some()
        || parsed.port().is_some()
        || parsed.query().is_some()
        || parsed.fragment().is_some()
    {
        return None;
    }

    if url.starts_with("https://installremote.timona.com.br/updates/")
        && parsed.host_str() == Some("installremote.timona.com.br")
    {
        let mut segments = parsed.path_segments()?;
        let folder = segments.next()?;
        let filename = segments.next()?;
        if folder != "updates" || segments.next().is_some() || !is_plain_update_filename(filename) {
            return None;
        }
        return Some(std::env::temp_dir().join(filename));
    }

    if !url.starts_with("https://github.com/") || parsed.host_str() != Some("github.com") {
        return None;
    }

    let mut segments = parsed.path_segments()?;
    let owner = segments.next()?;
    let repo = segments.next()?;
    let releases = segments.next()?;
    let download = segments.next()?;
    let tag = segments.next()?;
    let filename = segments.next()?;

    if owner != "rustdesk"
        || repo != "rustdesk"
        || releases != "releases"
        || download != "download"
        || tag.is_empty()
        || segments.next().is_some()
        || !is_plain_update_filename(filename)
    {
        return None;
    }

    Some(std::env::temp_dir().join(filename))""",
                "allow strict TIMONA OTA update download URL",
            ),
        ],
    )

    patch_file(
        "flutter/lib/desktop/widgets/update_progress.dart",
        [
            (
                "regex",
                r"downloadUrl = '[^']+';",
                "downloadUrl = 'https://installremote.timona.com.br/updates/$downloadFile';",
                "use direct TIMONA updates URL in update_progress.dart",
                0,
            ),
        ],
    )

    patch_file(
        "flutter/lib/desktop/pages/desktop_home_page.dart",
        [
            (
                "exact",
                """    if (!bind.isCustomClient() &&
        updateUrl.isNotEmpty &&
        !isCardClosed &&
        bind.mainUriPrefixSync().contains('rustdesk')) {""",
                "    if (updateUrl.isNotEmpty && !isCardClosed) {",
                "enable update banner for TIMONA Remote custom client",
            ),
            (
                "regex",
                r"final Uri url = Uri\.parse\('[^']+'\);",
                "final Uri url = Uri.parse('https://installremote.timona.com.br/updates/TimonaRemote-latest.exe');",
                "update fallback download link",
                0,
            ),
            (
                "exact",
                """          link: isToUpdate
              ? 'https://github.com/rustdesk/rustdesk/releases/tag/${bind.mainGetNewVersion()}'
              : null);""",
                """          link: isToUpdate
              ? 'https://installremote.timona.com.br/updates/version.json'
              : null);""",
                "replace github changelog url",
            ),
        ],
    )


def patch_settings_and_whitelabel():
    patch_file(
        "flutter/lib/desktop/pages/desktop_setting_page.dart",
        [
            (
                "exact",
                """class _GeneralState extends State<_General> {
  final RxBool serviceStop =
      isWeb ? RxBool(false) : Get.find<RxBool>(tag: 'stop-service');
  RxBool serviceBtnEnabled = true.obs;
  final GlobalKey _minToolbarOptionKey = GlobalKey();""",
                """class _GeneralState extends State<_General> {
  final RxBool serviceStop =
      isWeb ? RxBool(false) : Get.find<RxBool>(tag: 'stop-service');
  RxBool serviceBtnEnabled = true.obs;
  final GlobalKey _minToolbarOptionKey = GlobalKey();
  late final TextEditingController _techProfileController =
      TextEditingController(
          text: isWeb ? '' : bind.mainGetLocalOption(key: 'custom_technician_name'));

  @override
  void dispose() {
    _techProfileController.dispose();
    super.dispose();
  }""",
                "add technician profile controller to _GeneralState",
            ),
            (
                "exact",
                """      children: [
        if (!isWeb) service(),
        theme(),""",
                """      children: [
        if (!isWeb) technicianProfile(),
        if (!isWeb) service(),
        theme(),""",
                "add technicianProfile card in General settings",
            ),
            (
                "exact",
                "  Widget theme() {",
                """  Widget technicianProfile() {
    return _Card(
      title: 'Perfil do Técnico',
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: _kContentHMargin),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Nome exibido ao usuário ao solicitar suporte remoto:',
                style: Theme.of(context).textTheme.bodySmall,
              ).marginOnly(bottom: 8),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _techProfileController,
                      decoration: const InputDecoration(
                        hintText: 'Ex: Suporte TIMONA - Técnico',
                        isDense: true,
                        contentPadding:
                            EdgeInsets.symmetric(vertical: 10, horizontal: 12),
                      ),
                    ).workaroundFreezeLinuxMint().marginOnly(right: 12),
                  ),
                  ElevatedButton(
                    onPressed: () async {
                      await bind.mainSetLocalOption(
                          key: 'custom_technician_name',
                          value: _techProfileController.text.trim());
                      showToast(translate('Successful'));
                    },
                    child: Text(translate('Apply')),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget theme() {""",
                "implement technicianProfile card widget",
            ),
            (
                "exact",
                """    final showAutoUpdate = (isWindows && bind.mainIsInstalled()) ||
    (isMacOS && bind.mainIsInstalled() && bind.mainIsInstalledDaemon(prompt: false) && !bind.isCustomClient());""",
                "    final showAutoUpdate = (isWindows && bind.mainIsInstalled());",
                "enable Auto update option on Windows custom client",
            ),
            (
                "exact",
                "      if (!isWeb && !bind.isCustomClient())\n        _OptionCheckBox(\n          context,\n          'Check for software update on startup',",
                "      if (!isWeb)\n        _OptionCheckBox(\n          context,\n          'Check for software update on startup',",
                "enable Check for update toggle on custom client",
            ),
            (
                "exact",
                "child: _Card(title: translate('About RustDesk'), children: [",
                "child: _Card(title: 'Sobre TIMONA Remote', children: [",
                "white-label About card title",
            ),
            (
                "regex_optional",
                r"Purslane Tech Pte\. Ltd\.|Purslane Ltd",
                "TIMONA Tecnologia / Support TI",
                "white-label About copyright if not yet replaced",
                0,
            ),
        ],
    )

    patch_file(
        "flutter/lib/common.dart",
        [
            (
                "regex",
                r"Widget loadPowered\(BuildContext context\) \{.*?translate\(\"powered_by_me\"\),",
                """Widget loadPowered(BuildContext context) {
  if (bind.mainGetBuildinOption(key: "hide-powered-by-me") == 'Y') {
    return SizedBox.shrink();
  }
  return MouseRegion(
    cursor: SystemMouseCursors.click,
    child: GestureDetector(
      onTap: () {
        launchUrl(Uri.parse('https://www.supportti.net/'));
      },
      child: Opacity(
          opacity: 0.5,
          child: Text(
            "TIMONA Remote — Support TI",""",
                "white-label loadPowered footer",
                re.DOTALL,
            ),
        ],
    )

    # White-label portable cache folder prefix (AppData\Local\timonaremote / timona)
    patch_file(
        "libs/portable/src/main.rs",
        [
            (
                "regex",
                r'const APP_PREFIX: &str = "[^"]+";',
                'const APP_PREFIX: &str = "timona";',
                "portable extraction fallback folder",
                0,
            ),
        ],
    )

    # Global white-label replacement across translation value strings (keeps lookup keys intact!)
    lang_count = 0
    for lang_file in glob.glob("src/lang/*.rs"):
        with open(lang_file, "r", encoding="utf-8") as f:
            orig = f.read()
        updated_lines = []
        for line in orig.splitlines(keepends=True):
            if '", "' in line and ("RustDesk" in line or "rustdesk.com" in line or "RTIMONA" in line or "TimonaRemote" in line):
                key_part, val_part = line.split('", "', 1)
                val_part = val_part.replace("RustDesk", "TIMONA Remote")
                val_part = val_part.replace("rustdesk.com", "supportti.net")
                val_part = val_part.replace("RTIMONA", "TIMONA Remote")
                val_part = val_part.replace("TimonaRemote", "TIMONA Remote")
                line = f'{key_part}", "{val_part}'
            updated_lines.append(line)
        new_content = "".join(updated_lines)
        if new_content != orig:
            with open(lang_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            lang_count += 1
    print(f"[OK] White-labeled translation values in {lang_count} language files")

    # White-label hardcoded AppData / Staging / Runner metadata / Org
    patch_file(
        "libs/hbb_common/src/config.rs",
        [
            (
                "exact",
                '    pub static ref ORG: RwLock<String> = RwLock::new("com.carriez".to_owned());',
                '    pub static ref ORG: RwLock<String> = RwLock::new("br.com.timona".to_owned());',
                "white-label hbb_common ORG",
            ),
            (
                "exact",
                '    pub static ref APP_NAME: RwLock<String> = RwLock::new("RustDesk".to_owned());',
                '    pub static ref APP_NAME: RwLock<String> = RwLock::new("TimonaRemote".to_owned());',
                "white-label default APP_NAME before custom config loads",
            ),
        ],
    )

    patch_file(
        "src/platform/windows.rs",
        [
            (
                "exact",
                '    get_public_base_dir()\n        .join("RustDesk")\n        .join("RustDeskCustomClientStaging")',
                '    get_public_base_dir()\n        .join("TimonaRemote")\n        .join("TimonaRemoteCustomClientStaging")',
                "white-label ProgramData staging folder",
            ),
            (
                "exact",
                '        .join("rustdesk-sciter");\n    let dst = dir.join("rustdesk.exe");',
                '        .join("timonaremote-sciter");\n    let dst = dir.join("TimonaRemote.exe");',
                "white-label portable sciter helper folder",
            ),
        ],
    )

    patch_file(
        "flutter/windows/runner/Runner.rc",
        [
            (
                "regex_optional",
                r'Purslane Tech Pte\. Ltd\.|Purslane Ltd',
                'TIMONA Tecnologia',
                "white-label Runner.rc CompanyName/Copyright",
                0,
            ),
            (
                "regex_optional",
                r'VALUE "FileDescription", "[^"]*"',
                'VALUE "FileDescription", "TIMONA Remote"',
                "white-label Runner.rc FileDescription",
                0,
            ),
            (
                "regex_optional",
                r'VALUE "InternalName", "[^"]*"',
                'VALUE "InternalName", "TimonaRemote"',
                "white-label Runner.rc InternalName",
                0,
            ),
            (
                "regex_optional",
                r'VALUE "OriginalFilename", "[^"]*"',
                'VALUE "OriginalFilename", "TimonaRemote.exe"',
                "white-label Runner.rc OriginalFilename",
                0,
            ),
            (
                "regex_optional",
                r'VALUE "ProductName", "[^"]*"',
                'VALUE "ProductName", "TIMONA Remote"',
                "white-label Runner.rc ProductName",
                0,
            ),
        ],
    )

    patch_file(
        "libs/base/src/platform/mod.rs",
        [
            (
                "exact",
                '        linux::system_message(\n            "RustDesk",',
                '        linux::system_message(\n            "TIMONA Remote",',
                "white-label crash alert app name",
            ),
        ],
    )


def patch_unified_tray_suppression():
    # Quando instalado dentro de Timona-Unified-Agent (SupportTI.exe ao lado), suprime o segundo icone de tray
    patch_file(
        "src/common.rs",
        [
            (
                "exact",
                "#[inline]\npub fn is_custom_client() -> bool {",
                """#[inline]
pub fn is_unified_timona_agent() -> bool {
    std::env::current_exe()
        .ok()
        .and_then(|p| {
            p.parent()
                .and_then(|d| d.parent())
                .map(|root| root.join("SupportTI.exe").is_file())
        })
        .unwrap_or(false)
}

#[inline]
pub fn is_custom_client() -> bool {""",
                "add is_unified_timona_agent detection helper",
            ),
        ],
    )

    patch_file(
        "src/tray.rs",
        [
            (
                "exact",
                '    if crate::ui_interface::get_builtin_option(keys::OPTION_HIDE_TRAY) == "Y" {',
                '    if crate::ui_interface::get_builtin_option(keys::OPTION_HIDE_TRAY) == "Y"\n        || crate::common::is_unified_timona_agent()\n    {',
                "suppress duplicate tray icon when running under unified SupportTI agent",
            ),
        ],
    )

    patch_file(
        "src/core_main.rs",
        [
            (
                "exact",
                '        if should_check_start_tray && !crate::check_process("--tray", true) {',
                '        if should_check_start_tray && !crate::common::is_unified_timona_agent() && !crate::check_process("--tray", true) {',
                "skip launching redundant tray from main window when unified",
            ),
            (
                "exact",
                '        } else if args[0] == "--tray" {\n            if !crate::check_process("--tray", true) {',
                '        } else if args[0] == "--tray" {\n            if !crate::common::is_unified_timona_agent() && !crate::check_process("--tray", true) {',
                "skip --tray invocation when unified",
            ),
        ],
    )

    patch_file(
        "src/server/connection.rs",
        [
            (
                "exact",
                '                if crate::is_server() && !crate::check_process("--tray", false) {',
                '                if crate::is_server() && !crate::common::is_unified_timona_agent() && !crate::check_process("--tray", false) {',
                "skip spawning redundant tray from server connection loop when unified",
            ),
        ],
    )


if __name__ == "__main__":
    patch_connection_rs()
    patch_client_rs()
    patch_server_page_dart()
    patch_technician_preaccept_chat()
    patch_ota_updates()
    patch_settings_and_whitelabel()
    patch_unified_tray_suppression()
    print("[TIMONA] All customizations applied successfully.")
