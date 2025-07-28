-----

# Inky Display Slideshow

**Raspberry Pi** と **Pimoroni Inky Impression 5.7インチ**電子ペーパーディスプレイを使用して、指定したフォルダ内の画像をスライドショー表示するPythonスクリプトです。

画像には、EXIF情報から取得した撮影日と、現在からの経過時間をオーバーレイ表示します。

## ✨ 主な機能

  * **スライドショー**: 指定したディレクトリ内の画像（JPG, PNG）をランダムな順序で表示します。
  * **日付オーバーレイ**: 画像のEXIF情報から撮影日時を読み取り、画面の四隅のいずれかにランダムで表示します。
  * **経過時間表示**: 撮影日から現在までの経過時間（例: "3 years ago"）を日付と共に表示します。
  * **自動リサイズ**: ディスプレイの解像度に合わせて画像を自動でリサイズ・中央トリミングします。
  * **設定の外部化**: 表示間隔や画像フォルダのパスなどを`.env`ファイルで簡単に変更できます。
  * **ログ出力**: 動作状況やエラーをコンソールとログファイル（`~/.logs/slideshow_logs/slideshow.log`）に出力します。

-----

## ⚙️ 必要なもの

### ハードウェア

  * **Raspberry Pi** （任意のモデル）
  * **電子ペーパーディスプレイ**: [Pimoroni Inky Impression 5.7"](https://shop.pimoroni.com/products/inky-impression-5-7?variant=32298701324371)

### ソフトウェア

  * Python 3
  * 以下のPythonライブラリ
      * `inky`
      * `Pillow`
      * `piexif`
      * `python-dotenv`

-----

## 🚀 セットアップ

### 1\. ライブラリのインストール

必要なライブラリをpipでインストールします。

```sh
pip install inky pillow piexif python-dotenv
```

### 2\. ファイルの配置

プロジェクトディレクトリを以下のような構造で配置します。

```
my-slideshow/
├── slideshow.py    # このスクリプト
├── images/           # 表示させたい画像を入れるフォルダ
│   ├── photo1.jpg
│   └── photo2.png
└── .env              # 設定ファイル
```

### 3\. 設定ファイルの作成

`slideshow.py` と同じ階層に `.env` という名前のファイルを作成し、設定を記述します。

**`.env` ファイルの例:**

```ini
# 表示する画像が入っているフォルダ名
PHOTO_DIR="images"

# 画像を切り替える間隔（秒）
INTERVAL_SECONDS=1800

# （オプション）フォントファイルのフルパス
# FONT_PATH="/path/to/your/font.ttf"
```

  * `PHOTO_DIR` には、`slideshow.py`からの相対的な画像フォルダのパスを指定します。
  * `INTERVAL_SECONDS` はお好みの秒数に設定してください（例: 30分 = 1800秒）。

-----

## ▶️ 実行方法

以下のコマンドでスクリプトを実行します。`Ctrl+C`で終了するまで、設定した間隔で画像の表示を更新し続けます。

```sh
python3 slideshow.py
```

デーモン化してバックグラウンドで永続的に実行したい場合は、`tmux` や `systemd` を利用することをお勧めします。
