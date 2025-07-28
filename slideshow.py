#!/usr/bin/python3

"""
================================================================================
          Inky Impression - 高機能スライドショー スクリプト
================================================================================

概要 (Overview)
--------------------------------------------------------------------------------
このスクリプトは、Raspberry Piに接続されたPimoroni社の電子ペーパーディスプレイ
「Inky Impression」を、インテリジェントなデジタルフォトフレームとして機能させる
ためのプログラムです。指定されたフォルダから画像を読み込み、カスタマイズ可能な
オーバーレイ情報を付加して、順番に表示します。


主要機能 (Key Features)
--------------------------------------------------------------------------------
- **インテリジェントな表示キュー**:
  一度表示した画像は、すべての画像が表示されるまで再表示されません。
  これにより、短期間での画像の偏りを防ぎ、全ての思い出を均等に楽しめます。

- **状態の永続化**:
  表示待ちの画像リスト（キュー）はJSONファイルに保存されます。スクリプトが
  再起動（例：電源のOFF/ON）しても、前回の続きからスライドショーを
  再開するため、同じ画像を何度も見る必要がありません。

- **画像フォルダの自動検知**:
  起動時に画像フォルダ内のファイル数を確認します。前回実行時から画像の
  追加や削除があった場合、表示キューを自動的にリセットし、新しい画像
  リストでスライドショーを開始します。

- **EXIFデータ活用による情報表示**:
  JPEG画像のEXIF（撮影情報）を読み取り、「撮影日」と「現在からの経過時間」
  （例：3 years ago）を自動で計算し、画像上に美しくオーバーレイ表示します。
  情報の表示位置は、画面の四隅からランダムで選択され、マンネリを防ぎます。

- **柔軟な外部設定**:
  画像の表示間隔、画像フォルダの場所、使用するフォントなどを`.env`という
  設定ファイルで簡単に変更できます。コードを直接編集する必要はありません。

- **詳細なロギング**:
  プログラムの起動、画像の表示、エラー発生などの主要な動作を、コンソールと
  ログファイルの両方に出力します。問題発生時の原因究明に役立ちます。


動作の仕組み (How it Works)
--------------------------------------------------------------------------------
1. **起動**:
   - `.env`ファイルから設定を読み込みます。
   - `~/.cache/slideshow_state.json`から前回の状態（残り画像キューと総数）を
     読み込みます。
   - 画像ディレクトリ内の現在のファイル数を取得します。
   - 現在のファイル数と、保存されていた総数を比較し、差異があれば状態を
     リセットします。

2. **メインループ**:
   - 表示キューが空の場合、画像ディレクトリをスキャンして全画像リストを
     作成し、シャッフルして新しいキューを生成します。
   - キューの先頭から画像パスを1つ取り出します。
   - 画像をディスプレイの解像度に合わせてリサイズ、トリミングします。
   - EXIFから日付を抽出し、オーバーレイ用のテキストを生成します。
   - 画像とテキストを合成し、ディスプレイに表示します。

3. **状態保存**:
   - 画像の表示に成功するたびに、残りの画像キューと現在のサイクルでの
     総画像数をJSONファイルに上書き保存します。これにより、どの時点でも
     安全に停止・再起動が可能です。


設定 (Configuration)
--------------------------------------------------------------------------------
- **`.env` ファイル**:
  - `PHOTO_DIR`: 画像が格納されているディレクトリ名。
  - `INTERVAL_SECONDS`: 画像を切り替える秒数。
  - `FONT_PATH`: オーバーレイ表示に使用するフォントの絶対パス（任意）。

- **スクリプト内定数 `CONFIG`**:
  - 彩度、コントラスト、文字サイズなど、より詳細な表示設定を調整できます。


ファイル構造 (File Structure)
--------------------------------------------------------------------------------
- `slideshow.py`: このスクリプト本体。
- `images/` (デフォルト): 表示したい画像（.jpg, .png）を置く場所。
- `.env`: ユーザーが変更可能な設定を記述するファイル。
- `~/.cache/slideshow_state.json`: 表示キューの状態を保存するファイル（自動生成）。
- `~/.logs/slideshow_logs/slideshow.log`: 動作ログが記録されるファイル（自動生成）。

================================================================================
"""


# ===== 標準ライブラリのインポート =====
import os
import time
import random
import logging
import json
from datetime import datetime

# ===== サードパーティライブラリのインポート =====
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import piexif
from inky.auto import auto
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# ==================== 設定定数（環境変数と固定値） ====================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.expanduser("~/.cache/slideshow_state.json")

CONFIG = {
    "PHOTO_DIR": os.path.join(SCRIPT_DIR, os.getenv("PHOTO_DIR", "images")),
    "FONT_PATH": os.getenv("FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    "INTERVAL_SECONDS": int(os.getenv("INTERVAL_SECONDS", 1607)),
    "FONT_SIZE": 14,
    "DATE_FONT_SIZE": 16,
    "DATE_POSITIONS": ['bottom-right', 'top-right', 'top-left', 'bottom-left'],
    "MARGIN": 15,
    "BACKGROUND_PADDING": 10,
    "TEXT_PADDING": 8,
    "MAX_RETRY_ATTEMPTS": 3,
    "SATURATION": 0.85,
    "CONTRAST": 1.15
}

# ==================== ログシステムの初期化 ====================
def setup_logging():
    log_dir = os.path.expanduser("~/.logs/slideshow_logs")
    os.makedirs(log_dir, exist_ok=True)
    try:
        os.chmod(log_dir, 0o700)
    except Exception:
        pass
    log_file = os.path.join(log_dir, "slideshow.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# ==================== 状態管理関数（機能拡張版） ====================
def save_state(queue, total_count):
    """現在の表示キューと総画像数をJSONファイルに保存する"""
    state = {
        "total_count": total_count,
        "queue": queue
    }
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
        logger.info(f"現在の状態を保存しました。残り: {len(queue)} / {total_count}枚")
    except Exception as e:
        logger.error(f"状態の保存に失敗しました: {e}")

def load_state():
    """JSONファイルから表示キューと総画像数を読み込む"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                # 新旧両方のフォーマットに対応
                if isinstance(state, dict):
                    count = state.get("total_count", 0)
                    queue = state.get("queue", [])
                    logger.info(f"前回の状態を読み込みました。残り: {len(queue)} / {count}枚")
                    return count, queue
                elif isinstance(state, list): # 古いフォーマットの場合
                    logger.info("古い状態ファイルを検出しました。")
                    return 0, state # total_countを0にして必ずリセットさせる
        except Exception as e:
            logger.error(f"状態の読み込みに失敗しました: {e}")
    return 0, [] # デフォルト値（総数0, 空のキュー）

# ==================== 画像処理関連関数（変更なし） ====================
def extract_capture_date(image_path):
    file_ext = os.path.splitext(image_path)[1].lower()
    if file_ext == '.png': return None
    try:
        exif_dict = piexif.load(image_path)
        date_str = exif_dict['Exif'].get(piexif.ExifIFD.DateTimeOriginal)
        if date_str: return datetime.strptime(date_str.decode('utf-8'), "%Y:%m:%d %H:%M:%S")
        return None
    except Exception as e:
        logger.warning(f"EXIF取得エラー ({os.path.basename(image_path)}): {e}")
        return None

def format_date_and_elapsed_time(capture_date):
    if not capture_date: return "Unknown date", "Unknown date"
    formatted_date = capture_date.strftime("%Y-%m-%d")
    delta = datetime.now() - capture_date
    years = delta.days // 365
    if years > 0: elapsed = f"{years} year{'s' if years > 1 else ''} ago"
    else:
        months = delta.days // 30
        if months > 0: elapsed = f"{months} month{'s' if months > 1 else ''} ago"
        else: elapsed = "Within a month"
    return formatted_date, elapsed

def enhance_image(img):
    return ImageEnhance.Contrast(img).enhance(CONFIG["CONTRAST"])

def add_date_overlay(img, capture_date, inky_display):
    draw = ImageDraw.Draw(img)
    elapsed_font = ImageFont.truetype(CONFIG["FONT_PATH"], CONFIG["FONT_SIZE"])
    date_font = ImageFont.truetype(CONFIG["FONT_PATH"], CONFIG["DATE_FONT_SIZE"])
    formatted_date, elapsed_time = format_date_and_elapsed_time(capture_date)
    date_bbox = draw.textbbox((0,0), formatted_date, font=date_font)
    elapsed_bbox = draw.textbbox((0,0), elapsed_time, font=elapsed_font)
    max_width = max(date_bbox[2], elapsed_bbox[2])
    date_height, elapsed_height = date_bbox[3] - date_bbox[1], elapsed_bbox[3] - elapsed_bbox[1]
    total_height = date_height + elapsed_height + CONFIG["TEXT_PADDING"]
    margin, padding = CONFIG["MARGIN"], CONFIG["BACKGROUND_PADDING"]
    position = random.choice(CONFIG["DATE_POSITIONS"])
    if position == 'bottom-right': x, y = img.width - max_width - margin - padding, img.height - total_height - margin - padding
    elif position == 'top-right': x, y = img.width - max_width - margin - padding, margin + padding
    elif position == 'top-left': x, y = margin + padding, margin + padding
    else: x, y = margin + padding, img.height - total_height - margin - padding
    bg_left, bg_top = x - padding, y - padding
    bg_right, bg_bottom = x + max_width + padding, y + total_height + padding
    draw.rectangle((bg_left, bg_top, bg_right, bg_bottom), fill="white")
    draw.text((x, y), formatted_date, fill="black", font=date_font)
    draw.text((x, y + date_height + CONFIG["TEXT_PADDING"]), elapsed_time, fill="black", font=elapsed_font)
    return img

def prepare_image(image_path, inky_display):
    try:
        target_width, target_height = inky_display.width, inky_display.height
        logger.info(f"画像処理開始: {os.path.basename(image_path)}")
        with Image.open(image_path) as original_img:
            rgb_img = original_img.convert('RGB')
            enhanced_img = enhance_image(rgb_img)
            img_ratio = enhanced_img.width / enhanced_img.height
            target_ratio = target_width / target_height
            if img_ratio > target_ratio: new_height, new_width = target_height, int(target_height * img_ratio)
            else: new_width, new_height = target_width, int(target_width / img_ratio)
            resized_img = enhanced_img.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)
            left, top = (new_width - target_width) // 2, (new_height - target_height) // 2
            cropped_img = resized_img.crop((left, top, left + target_width, top + target_height))
            capture_date = extract_capture_date(image_path)
            return add_date_overlay(cropped_img, capture_date, inky_display)
    except Exception as e:
        logger.error(f"画像処理エラー [{os.path.basename(image_path)}]: {str(e)[:100]}")
        return None

# ==================== メイン処理ループ（状態保存・自動リセット対応版） ====================
def main():
    logger.info("=== Inkyスライドショーを起動します ===")
    try:
        inky_display = auto()
        inky_display.set_border(inky_display.WHITE)
        logger.info(f"検出されたディスプレイ: {inky_display} 解像度: {inky_display.width}x{inky_display.height}")
    except Exception as e:
        logger.error(f"ディスプレイ初期化エラー: {e}")
        return

    photo_dir = CONFIG["PHOTO_DIR"]
    if not os.path.isdir(photo_dir):
        logger.error(f"画像ディレクトリが見つかりません: {photo_dir}")
        return

    # 現在の画像ファイルリストと数を取得
    current_files = [os.path.join(photo_dir, f) for f in os.listdir(photo_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    current_file_count = len(current_files)

    # 状態を読み込む
    saved_count, display_queue = load_state()

    # 現在のファイル数と保存された総数を比較
    if current_file_count != saved_count:
        logger.info(f"画像数の変動を検知しました (前回:{saved_count} -> 現在:{current_file_count})。キューをリセットします。")
        display_queue = [] # キューを空にしてリセットを強制

    total_in_cycle = current_file_count

    while True:
        try:
            if not display_queue:
                logger.info("表示キューが空です。全画像リストを再生成します。")
                all_files = [os.path.join(photo_dir, f) for f in os.listdir(photo_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                if not all_files:
                    logger.error(f"画像ファイルが見つかりませんでした: {photo_dir}")
                    if os.path.exists(STATE_FILE): os.remove(STATE_FILE) # 状態ファイルも削除
                    time.sleep(60)
                    continue
                
                random.shuffle(all_files)
                display_queue = all_files
                total_in_cycle = len(display_queue)

            image_path = display_queue.pop(0)
            
            logger.info(f"表示処理開始: {os.path.basename(image_path)}")
            processed_image = prepare_image(image_path, inky_display)

            if processed_image:
                try:
                    inky_display.set_image(processed_image, saturation=CONFIG["SATURATION"])
                    inky_display.show()
                    logger.info(f"表示に成功しました: {os.path.basename(image_path)}")
                    save_state(display_queue, total_in_cycle)
                except Exception as e:
                    logger.error(f"表示エラー: {str(e)[:100]}")
                    display_queue.insert(0, image_path) # 失敗した場合はキューに戻す
            
            time.sleep(CONFIG["INTERVAL_SECONDS"])

        except KeyboardInterrupt:
            logger.info("ユーザーの操作により中断されました")
            break
        except Exception as e:
            logger.error(f"致命的なエラーが発生しました: {str(e)[:100]}")
            time.sleep(10)

if __name__ == "__main__":
    main()
    logger.info("=== プログラムを正常終了します ===")
