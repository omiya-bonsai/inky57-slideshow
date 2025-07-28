# Inky Impression 高機能スライドショー

Raspberry Piに接続されたPimoroni社の電子ペーパーディスプレイ「Inky Impression 5.7" (7 colour ePaper/eInk HAT)」を、インテリジェントなデジタルフォトフレームとして機能させるためのPythonスクリプトです。

## 🌟 主要機能

### インテリジェントな表示システム
- **スマートキュー管理**: 一度表示した画像は、すべての画像が表示されるまで再表示されません
- **状態の永続化**: スクリプトの再起動後も前回の続きから表示を再開
- **自動リセット機能**: 画像フォルダ内のファイル変更を検知し、表示キューを自動更新

### EXIF情報を活用した美しい表示
- **撮影日の自動表示**: JPEG画像のEXIF情報から撮影日を抽出
- **経過時間の計算**: 「3 years ago」のような分かりやすい経過時間を表示
- **ランダム配置**: 日付情報を画面の四隅にランダム配置してマンネリを防止

### 柔軟な設定システム
- **外部設定ファイル**: `.env`ファイルで簡単に設定変更
- **詳細な画像調整**: 彩度、コントラスト、フォントサイズなどの細かな調整が可能
- **包括的なログ出力**: 動作状況とエラーの詳細な記録

## 📋 必要な環境

### ハードウェア
- Raspberry Pi（3B+以降推奨）
- **[Pimoroni Inky Impression 5.7"]**(https://shop.pimoroni.com/products/inky-impression-5-7?variant=32298701324371)（7色電子ペーパーディスプレイ）

### ソフトウェア
- Python 3.7以降
- 必要なPythonパッケージ（requirements.txtを参照）

## 🚀 インストール

### 1. リポジトリのクローン
```bash
git clone https://github.com/omiya-bonsai/inky57-slideshow.git
cd inky-slideshow
```

### 2. 依存パッケージのインストール
```bash
pip install -r requirements.txt
```

### 3. 設定ファイルの作成
```bash
cp .env.sample .env
```

### 4. 画像フォルダの準備
```bash
mkdir images
# お気に入りの写真（.jpg, .jpeg, .png）をimagesフォルダに配置
```

## ⚙️ 設定

`.env`ファイルを編集して、お好みに合わせて設定を調整してください：

```env
# 画像が格納されているディレクトリ名
PHOTO_DIR="images"

# 画像切り替え間隔（秒）
# 例：30分 = 1800秒
INTERVAL_SECONDS=1800

# カスタムフォントのパス（オプション）
# FONT_PATH="/path/to/your/custom-font.ttf"
```

### 詳細設定

スクリプト内の`CONFIG`定数を編集することで、以下の項目も調整できます：
- フォントサイズ
- 彩度・コントラスト
- 日付表示の余白
- リトライ回数

## 🖼️ 使用方法

### 基本実行
```bash
python3 slideshow.py
```

### バックグラウンド実行
```bash
nohup python3 slideshow.py &
```

### systemdサービスとして実行（推奨）
サービスファイルの例：
```ini
[Unit]
Description=Inky Impression Slideshow
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/inky57-slideshow
ExecStart=/usr/bin/python3 /home/pi/inky57-slideshow/slideshow.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 📁 ファイル構造

```
inky57-slideshow/
├── slideshow.py          # メインスクリプト
├── .env                  # 設定ファイル
├── .env.sample          # 設定ファイルのサンプル
├── images/              # 画像フォルダ（デフォルト）
├── requirements.txt     # Python依存パッケージ
├── README.md           # このファイル
└── LICENSE             # MITライセンス
```

### 自動生成されるファイル
- `~/.cache/slideshow_state.json` - 表示状態の保存
- `~/.logs/slideshow_logs/slideshow.log` - 動作ログ

## 🔧 トラブルシューティング

### よくある問題

**Q: 画像が表示されない**
A: 以下を確認してください：
- 画像ファイルが`.jpg`, `.jpeg`, `.png`形式であること
- `images`フォルダに画像が配置されていること
- Inky Impressionが正しく接続されていること

**Q: 日付が表示されない**
A: PNG画像にはEXIF情報が含まれていないため、「Unknown date」と表示されます。これは正常な動作です。

**Q: フォントが見つからないエラー**
A: `.env`ファイルで`FONT_PATH`を正しいフォントファイルのパスに設定してください。

### ログの確認
```bash
tail -f ~/.logs/slideshow_logs/slideshow.log
```

## 📸 対応画像形式

- JPEG (.jpg, .jpeg) - EXIFデータから撮影日を取得
- PNG (.png) - 撮影日は「Unknown date」として表示

## 🤝 コントリビューション

プルリクエスト、イシューの報告、機能提案など、どんな形でもコントリビューションを歓迎します！

## 📄 ライセンス

このプロジェクトは[MIT License](LICENSE)の下で公開されています。

## 🙏 謝辞

このプロジェクトの開発にあたり、以下のツールとサービスを活用させていただきました：

- **[Pimoroni](https://pimoroni.com/)** - 素晴らしいInky Impressionディスプレイの提供
- **[Raspberry Pi Foundation](https://www.raspberrypi.org/)** - 優れたシングルボードコンピュータの開発
- **Google Gemini** - コード開発とデバッグにおけるAIアシスタンス
- **Anthropic Claude** - ドキュメント作成とコード改善におけるAIサポート

また、オープンソースコミュニティの皆様、特にPIL（Pillow）、piexif、python-dotenvなどのライブラリ開発者の皆様に深く感謝いたします。

---

**Made with ❤️ for preserving memories**
