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
    # Lado do tecnico: inicializar ChatModel no pre-aceite e liberar barra superior estilo AnyDesk
    patch_file(
        "flutter/lib/models/model.dart",
        [
            (
                "exact",
                """    if (type == 're-input-password') {
      wrongPasswordDialog(sessionId, dialogManager, type, title, text);
    } else if (type == 'input-2fa') {
      enter2FaDialog(sessionId, dialogManager);
    } else if (type == 'input-password') {
      enterPasswordDialog(sessionId, dialogManager);""",
                """    if (type == 're-input-password') {
      parent.target?.chatModel
          .changeCurrentKey(MessageKey(peerId, ChatModel.clientModeID));
      wrongPasswordDialog(sessionId, dialogManager, type, title, text);
    } else if (type == 'input-2fa') {
      enter2FaDialog(sessionId, dialogManager);
    } else if (type == 'input-password') {
      parent.target?.chatModel
          .changeCurrentKey(MessageKey(peerId, ChatModel.clientModeID));
      enterPasswordDialog(sessionId, dialogManager);""",
                "initialize client chat key on password dialogs in model.dart",
            ),
            (
                "exact",
                "    } else if (type == 'wait-remote-accept-nook') {\n      showWaitAcceptDialog(sessionId, type, title, text, dialogManager);",
                """    } else if (type == 'wait-remote-accept-nook') {
      parent.target?.chatModel
          .changeCurrentKey(MessageKey(peerId, ChatModel.clientModeID));
      showWaitAcceptDialog(sessionId, type, title, text, dialogManager);""",
                "initialize client chat key on wait-remote-accept-nook",
            ),
        ],
    )

    # Permitir que a barra superior fique clicavel acima do modal de senha/espera
    patch_file(
        "flutter/lib/desktop/pages/remote_page.dart",
        [
            (
                "exact",
                """              Obx(() => _ffi.inputModel.relativeMouseMode.value
                  ? const Offstage()
                  : _ffi.ffiModel.pi.isSet.isTrue
                      ? Overlay(initialEntries: [
                          OverlayEntry(builder: remoteToolbar)
                        ])
                      : remoteToolbar(context)),
              _ffi.ffiModel.pi.isSet.isFalse ? emptyOverlay() : Offstage(),""",
                """              _ffi.ffiModel.pi.isSet.isFalse ? emptyOverlay() : Offstage(),
              Obx(() => _ffi.inputModel.relativeMouseMode.value
                  ? const Offstage()
                  : Overlay(initialEntries: [
                      OverlayEntry(builder: remoteToolbar)
                    ])),""",
                "render RemoteToolbar above pre-accept modal overlay",
            ),
        ],
    )

    # Barra superior estilo AnyDesk: visual limpo com ID a esquerda, icones apagadinhos no pre-aceite e Chat+Fechar ativos
    patch_file(
        "flutter/lib/desktop/widgets/remote_toolbar.dart",
        [
            (
                "exact",
                """  Widget _buildToolbar(
      BuildContext context, _ToolbarEdge edge, bool isHorizontal) {
    final List<Widget> toolbarItems = [];
    toolbarItems.add(_PinMenu(state: widget.state));
    toolbarItems.add(Obx(() {
      final privacyModeState = PrivacyModeState.find(widget.id);
      if ((privacyModeState.isEmpty ||
              allowDisplaySwitchInPrivacyMode(pi, privacyModeState.value)) &&
          pi.displaysCount.value > 1 &&
          mainGetLocalBoolOptionSync(kOptionAllowMonitorSwitchMainToolbar)) {
        return _MainMonitorSwitchButton(id: widget.id, ffi: widget.ffi);
      } else {
        return const Offstage();
      }
    }));
    if (!isWebDesktop) {
      toolbarItems.add(_MobileActionMenu(ffi: widget.ffi));
    }

    toolbarItems.add(Obx(() {
      final privacyModeState = PrivacyModeState.find(widget.id);
      if ((privacyModeState.isEmpty ||
              allowDisplaySwitchInPrivacyMode(pi, privacyModeState.value)) &&
          pi.displaysCount.value > 1) {
        return _MonitorMenu(
            id: widget.id,
            ffi: widget.ffi,
            edge: edge,
            setRemoteState: widget.setRemoteState);
      } else {
        return Offstage();
      }
    }));

    toolbarItems
        .add(_ControlMenu(id: widget.id, ffi: widget.ffi, state: widget.state));
    toolbarItems.add(_DisplayMenu(
      id: widget.id,
      ffi: widget.ffi,
      state: widget.state,
      setFullscreen: _setFullscreen,
    ));
    // Do not show keyboard for camera connection type.
    if (widget.ffi.connType == ConnType.defaultConn) {
      toolbarItems.add(_KeyboardMenu(id: widget.id, ffi: widget.ffi));
    }
    toolbarItems.add(_ChatMenu(id: widget.id, ffi: widget.ffi));
    if (!isWeb) {
      toolbarItems.add(_VoiceCallMenu(id: widget.id, ffi: widget.ffi));
    }
    if (!isWeb) toolbarItems.add(_RecordMenu());
    toolbarItems.add(_CloseMenu(id: widget.id, ffi: widget.ffi));
    final toolbarBorderRadius = BorderRadius.all(Radius.circular(4.0));""",
                """  Widget _buildToolbar(
      BuildContext context, _ToolbarEdge edge, bool isHorizontal) {
    final bool isPreAccept = pi.isSet.isFalse;
    Widget preAcceptGuard(Widget child) => isPreAccept
        ? IgnorePointer(child: Opacity(opacity: 0.30, child: child))
        : child;

    final List<Widget> toolbarItems = [];
    if (isHorizontal) {
      toolbarItems.add(Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isPreAccept
                    ? const Color(0xFFF59E0B)
                    : const Color(0xFF16A34A),
              ),
            ),
            const SizedBox(width: 8),
            Container(width: 1, height: 16, color: Theme.of(context).dividerColor),
            const SizedBox(width: 8),
            Text(
              widget.ffi.id,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
            ),
            const SizedBox(width: 6),
          ],
        ),
      ));
    }
    toolbarItems.add(_PinMenu(state: widget.state));
    toolbarItems.add(preAcceptGuard(Obx(() {
      final privacyModeState = PrivacyModeState.find(widget.id);
      if ((privacyModeState.isEmpty ||
              allowDisplaySwitchInPrivacyMode(pi, privacyModeState.value)) &&
          pi.displaysCount.value > 1 &&
          mainGetLocalBoolOptionSync(kOptionAllowMonitorSwitchMainToolbar)) {
        return _MainMonitorSwitchButton(id: widget.id, ffi: widget.ffi);
      } else {
        return const Offstage();
      }
    })));
    if (!isWebDesktop) {
      toolbarItems.add(preAcceptGuard(_MobileActionMenu(ffi: widget.ffi)));
    }

    toolbarItems.add(preAcceptGuard(Obx(() {
      final privacyModeState = PrivacyModeState.find(widget.id);
      if ((privacyModeState.isEmpty ||
              allowDisplaySwitchInPrivacyMode(pi, privacyModeState.value)) &&
          pi.displaysCount.value > 1) {
        return _MonitorMenu(
            id: widget.id,
            ffi: widget.ffi,
            edge: edge,
            setRemoteState: widget.setRemoteState);
      } else {
        return Offstage();
      }
    })));

    toolbarItems.add(preAcceptGuard(
        _ControlMenu(id: widget.id, ffi: widget.ffi, state: widget.state)));
    toolbarItems.add(preAcceptGuard(_DisplayMenu(
      id: widget.id,
      ffi: widget.ffi,
      state: widget.state,
      setFullscreen: _setFullscreen,
    )));
    // Do not show keyboard for camera connection type.
    if (widget.ffi.connType == ConnType.defaultConn) {
      toolbarItems.add(preAcceptGuard(_KeyboardMenu(id: widget.id, ffi: widget.ffi)));
    }
    toolbarItems.add(_ChatMenu(id: widget.id, ffi: widget.ffi));
    if (!isWeb) {
      toolbarItems.add(preAcceptGuard(_VoiceCallMenu(id: widget.id, ffi: widget.ffi)));
    }
    if (!isWeb) toolbarItems.add(preAcceptGuard(_RecordMenu()));
    toolbarItems.add(_CloseMenu(id: widget.id, ffi: widget.ffi));
    final toolbarBorderRadius = BorderRadius.all(Radius.circular(8.0));""",
                "style RemoteToolbar like AnyDesk with dimmed pre-accept controls and active Chat",
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
    if is_unified_timona_agent() {
        clear_software_update_url();
        return;
    }
    let opt = LocalConfig::get_option(keys::OPTION_ENABLE_CHECK_UPDATE);
    if config::option2bool(keys::OPTION_ENABLE_CHECK_UPDATE, &opt) {
        std::thread::spawn(move || allow_err!(do_check_software_update()));
    }
}""",
                "allow check_software_update in custom client",
            ),
            (
                "exact",
                """fn process_software_update_check_response(bytes: Bytes) -> ResultType<()> {
    let resp: hbb_common::VersionCheckResponse = serde_json::from_slice(&bytes)?;
    let response_url = resp.url;
    let release_id = release_id_from_update_url(&response_url)?;
    let latest_release_version = display_version_from_release_id(&release_id)?;""",
                """fn process_software_update_check_response(bytes: Bytes) -> ResultType<()> {
    let resp: serde_json::Value = serde_json::from_slice(&bytes)?;
    let latest_release_version = resp
        .get("version")
        .and_then(|v| v.as_str())
        .unwrap_or_default()
        .to_string();
    let response_url = if latest_release_version.is_empty() {
        String::new()
    } else {
        format!(
            "https://installremote.timona.com.br/updates/{}",
            latest_release_version
        )
    };
    if response_url.is_empty() {
        clear_software_update_url();
        return Ok(());
    }""",
                "parse proprietary version.json in process_software_update_check_response",
            ),
            (
                "exact",
                """pub async fn do_check_software_update() -> hbb_common::ResultType<()> {
    let (request, url) =
        hbb_common::version_check_request(hbb_common::VER_TYPE_RUSTDESK_CLIENT.to_string());
    let proxy_conf = Config::get_socks();
    let tls_url = get_url_for_tls(&url, &proxy_conf);
    let tls_type = get_cached_tls_type(tls_url);
    let is_tls_not_cached = tls_type.is_none();
    let tls_type = tls_type.unwrap_or(TlsType::Rustls);
    let client = create_http_client_async(tls_type, false);
    let latest_release_response: ResultType<_> = match client.post(&url).json(&request).send().await
    {
        Ok(resp) => Ok((tls_type, resp)),
        Err(err) => {
            if is_tls_not_cached && err.is_request() {
                let tls_type = TlsType::NativeTls;
                let client = create_http_client_async(tls_type, false);
                match client.post(&url).json(&request).send().await {
                    Ok(resp) => Ok((tls_type, resp)),
                    Err(err) => Err(err.into()),
                }
            } else {
                Err(err.into())
            }
        }
    };""",
                """pub async fn do_check_software_update() -> hbb_common::ResultType<()> {
    let url = "https://installremote.timona.com.br/updates/version.json".to_string();
    let proxy_conf = Config::get_socks();
    let tls_url = get_url_for_tls(&url, &proxy_conf);
    let tls_type = get_cached_tls_type(tls_url);
    let is_tls_not_cached = tls_type.is_none();
    let tls_type = tls_type.unwrap_or(TlsType::Rustls);
    let client = create_http_client_async(tls_type, false);
    let latest_release_response: ResultType<_> = match client.get(&url).send().await {
        Ok(resp) => Ok((tls_type, resp)),
        Err(err) => {
            if is_tls_not_cached && err.is_request() {
                let tls_type = TlsType::NativeTls;
                let client = create_http_client_async(tls_type, false);
                match client.get(&url).send().await {
                    Ok(resp) => Ok((tls_type, resp)),
                    Err(err) => Err(err.into()),
                }
            } else {
                Err(err.into())
            }
        }
    };""",
                "fetch proprietary version.json for OTA update check (1.5.3)",
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
        ],
    )

    patch_file(
        "src/updater/artifact.rs",
        [
            (
                "exact",
                """pub(super) fn verified_update_artifact_from_release_page_url(
    update_url: &str,
    query: &UpdateArtifactQuery<'_>,
) -> ResultType<VerifiedUpdateArtifact> {""",
                """pub(super) fn verified_update_artifact_from_release_page_url(
    update_url: &str,
    query: &UpdateArtifactQuery<'_>,
) -> ResultType<VerifiedUpdateArtifact> {
    if update_url.starts_with("https://installremote.timona.com.br/updates/") {
        let manifest_bytes =
            fetch_update_sidecar_bytes("https://installremote.timona.com.br/updates/version.json")?;
        let resp: serde_json::Value = serde_json::from_slice(&manifest_bytes)?;
        let version = resp
            .get("version")
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .to_string();
        let is_msi = query.format == "msi";
        let dl_url = resp
            .get(if is_msi { "url_msi" } else { "url" })
            .and_then(|v| v.as_str())
            .unwrap_or(if is_msi {
                "https://installremote.timona.com.br/updates/TimonaRemote-latest.msi"
            } else {
                "https://installremote.timona.com.br/updates/TimonaRemote-latest.exe"
            })
            .to_string();
        let size = resp
            .get(if is_msi { "size_msi" } else { "size" })
            .and_then(|v| v.as_u64())
            .unwrap_or(0);
        let sha256 = resp
            .get(if is_msi { "sha256_msi" } else { "sha256" })
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .to_string();
        return Ok(crate::update_metadata::VerifiedUpdateArtifact {
            version,
            url: dl_url,
            #[cfg(target_os = "macos")]
            file_name: String::new(),
            size,
            sha256,
        });
    }""",
                "verify TIMONA OTA manifest in artifact.rs",
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
                "allow strict TIMONA OTA update download URL in artifact.rs",
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

    patch_file(
        "src/platform/windows.rs",
        [
            (
                "exact",
                'fn get_install_info_with_subkey(subkey: String) -> (String, String, String, String) {\n    let mut path = get_reg_of(&subkey, "InstallLocation");',
                '''fn get_install_info_with_subkey(subkey: String) -> (String, String, String, String) {
    if crate::common::is_unified_timona_agent() {
        if let Ok(cur_exe) = std::env::current_exe() {
            if let Some(dir) = cur_exe.parent() {
                let path = dir.to_string_lossy().to_string();
                let exe = cur_exe.to_string_lossy().to_string();
                let start_menu = format!(
                    "%ProgramData%\\\\Microsoft\\\\Windows\\\\Start Menu\\\\Programs\\\\{}",
                    crate::get_app_name()
                );
                return (subkey, path, start_menu, exe);
            }
        }
    }
    let mut path = get_reg_of(&subkey, "InstallLocation");''',
                "report unified Program Files Timona Agent remote dir as installed",
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
