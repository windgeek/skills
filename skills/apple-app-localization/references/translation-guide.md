# Translation guide

The standing rules for translating any Apple-platform app. They live here, in
the skill, so no project needs its own `TRANSLATION.md`. What is specific to
one app goes into that app's String Catalog (see "Where project rules live").

## Where project rules live

- **Per string:** the entry's `comment` in the `.xcstrings`. Say what the
  string is for, where it appears, and anything a translator must not change
  ("this is a promise, translate literally"). Xcode's translation agent reads
  comments, and so does `dump_for_review.py`.
- **Per project:** a short "Localization" section in the project's own
  `AGENTS.md` / `CLAUDE.md`, or its README if it has neither. List the reference
  language, the tone rules and banned words, the key prefixes whose wording
  is a commitment, the terms that must stay consistent, and the test or
  script that enforces them. Keep it to a few lines. Don't restate anything
  in this guide.
- Before translating, read that section and the comments of the keys being
  translated.

## Tone

- **Calm and exact.** Say what is there and what happens next. Don't create
  urgency, don't alarm, don't promise results.
- **No claims App Review rejects.** Never say the device will be
  "optimized", "sped up", "fixed", "cleaned" or "protected" unless the app
  demonstrably does exactly that.
- **Written register, not chat.** Use the neutral register the OS itself uses
  in that language, with no colloquialisms. In Chinese, avoid 东西, 删掉, 搞,
  咱, 玩意 and similar.
- **Promises stay promises.** "Does not remove" never becomes "usually doesn't
  remove", and "usually" never disappears either. Conditions keep their exact
  strength.

## Address the user as the OS does

*du* in German, *vous* in French, *tú* in Spanish, *você* in Brazilian
Portuguese, です/ます in Japanese, 합니다체 in Korean, 你 in Chinese. Use the
same form everywhere in the app.

## Match the system's own words

Users compare the app with what Finder and System Settings say, and a term
that differs from the system's looks like a different thing. **Never translate
an OS term yourself. Look it up:**

```bash
python3 <skill>/scripts/system_terms.py "Quick Look" "Open With" "Spotlight"
```

The script reads the OS's own `.loctable` files and the Finder's strings on the
Mac it runs on. Where variants disagree, the Finder's or System Settings' own
string wins. The table below was verified on macOS 26.6. Re-check anything not
in it, and re-check it all after a major OS release.

| English | zh-Hans | zh-Hant | ja | ko | de | fr | es | pt-BR |
|---|---|---|---|---|---|---|---|---|
| Trash | 废纸篓 | 垃圾桶 | ゴミ箱 | 휴지통 | Papierkorb | Corbeille | Papelera | Lixo |
| Finder | 访达 | Finder | Finder | Finder | Finder | Finder | Finder | Finder |
| Dock | 程序坞 | Dock | Dock | Dock | Dock | Dock | Dock | Dock |
| Menu Bar | 菜单栏 | 選單列 | メニューバー | 메뉴 막대 | Menüleiste | Barre des menus | Barra de menús | Barra de Menus |
| Spotlight | 聚焦 | Spotlight | Spotlight | Spotlight | Spotlight | Spotlight | Spotlight | Spotlight |
| Quick Look | 快速查看 | 快速查看 | クイックルック | 훑어보기 | Übersicht | Coup d’œil | Vista rápida | Visualização Rápida |
| Open With | 打开方式 | 打開檔案的應用程式 | このアプリケーションで開く | 다음으로 열기 | Öffnen mit | Ouvrir avec | Abrir con | Abrir com |
| Activity Monitor | 活动监视器 | 活動監視器 | アクティビティモニタ | 활성 상태 보기 | Aktivitätsanzeige | Moniteur d’activité | Monitor de Actividad | Monitor de Atividade |
| Disk Utility | 磁盘工具 | 磁碟工具程式 | ディスクユーティリティ | 디스크 유틸리티 | Festplattendienstprogramm | Utilitaire de disque | Utilidad de Discos | Utilitário de Disco |
| Terminal | 终端 | 終端機 | ターミナル | 터미널 | Terminal | Terminal | Terminal | Terminal |
| System Settings | 系统设置 | 系統設定 | システム設定 | 시스템 설정 | Systemeinstellungen | Réglages Système | Ajustes del Sistema | Ajustes do Sistema |
| Sound (settings) | 声音 | 聲音 | サウンド | 사운드 | Ton | Son | Sonido | Som |
| Network (settings) | 网络 | 網路 | ネットワーク | 네트워크 | Netzwerk | Réseau | Red | Rede |
| DNS Servers | DNS服务器 | DNS伺服器 | DNSサーバ | DNS 서버 | DNS-Server | Serveurs DNS | Servidores DNS | Servidores DNS |
| System Integrity Protection | 系统完整性保护 | 系統完整保護 | システム整合性保護 | 시스템 무결성 보호 | Systemintegritätsschutz | Protection de l’intégrité du système | Protección de la integridad del sistema | Proteção de Integridade do Sistema |
| Thumbnails | 缩略图 | 縮覽圖 | サムネール | 썸네일 | Miniaturen | Vignettes | Miniaturas | Miniaturas |
| Applications (folder) | 应用程序 | 應用程式 | アプリケーション | 응용 프로그램 | Programme | Applications | Aplicaciones | Aplicativos |
| Login Items & Extensions | 登录项与扩展 | 登入項目與延伸功能 | ログイン項目と機能拡張 | 로그인 항목 및 확장 프로그램 | Anmeldeobjekte & Erweiterungen | Ouverture et extensions | Ítems de inicio y extensiones | Itens de Início de Sessão e Extensões |
| Full Disk Access | 完全磁盘访问权限 | 完全取用磁碟 | フルディスクアクセス | 전체 디스크 접근 권한 | Festplattenvollzugriff | Accès complet au disque | Acceso total al disco | Acesso Total ao Disco |
| Home folder | 个人文件夹 | 個人專屬檔案夾 | ホームフォルダ | 홈 폴더 | Benutzerordner | dossier de départ | carpeta de inicio | pasta pessoal |

## Never translate

- The app's name and other product or brand names (Xcode, Homebrew, Docker…).
  Chinese still uses 访达 and 程序坞 where the OS does.
- File paths, bundle identifiers, command names, and anything in backticks or
  quotes that names something on disk.
- Format specifiers (`%@`, `%lld`, `%1$@`, `%%`). Positional forms may be
  reordered; nothing else about them may change.

## Punctuation and typography

- French: a no-break space before `:` and inside « », and a narrow no-break
  space before `;` `?` `!`.
- Quotation marks: de „…“, fr « … », es «…», pt-BR “…”, ja 「…」, zh-Hans “…”,
  zh-Hant 「…」, ko ‘…’.
- CJK: full-width punctuation with no spaces around it. A list separator in a
  format string is `，` in Chinese and `、` in Japanese.
- The ellipsis character `…`, never three dots.

## Plurals and agreement

- Every count is a plural variation. Provide all the forms the language
  requires: `one`/`other` in de; `one`/`many`/`other` in fr, es, pt and it;
  `one`/`few`/`many`/`other` in ru and pl; only `other` in zh, ja and ko.
- An English participle that doesn't change with number ("%lld selected")
  becomes a plural adjective in Romance languages. Write it as a label
  ("Sélection : %lld") or add a plural variation for that language.

## Length

Buttons, tabs and row titles have fixed widths. German and French run about
30% longer than English. Shorten long labels by rewording, not by
abbreviating, and never shorten the system's own terms.
