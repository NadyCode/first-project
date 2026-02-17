# 病院アンケートシステム

病院向けオフライン・アンケートシステム。Windows デスクトップアプリケーション（.exe 形式）として動作し、院内 LAN の共有フォルダを利用してデータを管理します。

## 機能

- **アンケート作成（管理者モード）**: 単一選択・自由記述の設問作成、PDF 参照リンク、パスワード保護
- **アンケート回答**: 部署・氏名連動プルダウン、必須項目バリデーション
- **ログ収集**: 起動時に端末名・IP・日時を自動記録
- **集計・出力**: 回答データの自動集計、未回答者抽出、CSV エクスポート

## プロジェクト構成

```
├── main.py              # エントリポイント
├── src/
│   ├── app.py           # メインアプリケーション（GUI）
│   ├── config.py        # 設定定数
│   ├── data_manager.py  # データ読み書き（CSV/JSON）
│   ├── file_lock.py     # ファイルロック（排他制御）
│   ├── gui_admin.py     # 管理者モード画面
│   ├── gui_aggregate.py # 集計・出力画面
│   ├── gui_response.py  # 回答者モード画面
│   └── logger.py        # 操作ログ収集
├── data/
│   ├── master_user.csv  # 職員マスターデータ
│   └── survey_config.json # アンケート設問設定
├── tests/               # ユニットテスト
├── build.spec           # PyInstaller ビルド設定
└── requirements.txt     # 依存パッケージ
```

## 実行方法

```bash
python main.py
```

## exe ビルド

```bash
pip install -r requirements.txt
pyinstaller build.spec
```

`dist/HospitalSurvey.exe` が生成されます。

## テスト

```bash
python -m unittest discover -s tests -v
```

## データファイル

| ファイル | 用途 | 形式 |
|---|---|---|
| `master_user.csv` | 部署と氏名の紐付けリスト | CSV |
| `survey_config.json` | アンケートの設問設定 | JSON |
| `answers.csv` | 回答データの蓄積 | CSV |
| `access_log.txt` | 端末名・IP・時間のログ | Text |
