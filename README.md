# dev-template

開発環境テンプレ

## はじめに

VS Code でこのリポジトリを開き、`Dev Containers: Reopen in Container` を実行します。開発コンテナーには Node.js 24、npm、GitHub CLI、GitHub Copilot CLI、`uv`、`ripgrep` を含みます。

初回起動時に `@github/copilot` は自動でグローバルインストールされます。Copilot CLI の履歴、Copilot Chat の履歴、Google Antigravity の履歴は Docker ボリュームに永続化されます。

## テンプレートから新しいリポジトリを作る

### GitHub の画面から作る

1. [dev-template](https://github.com/high-soar/dev-template) を開きます。
2. **Use this template** → **Create a new repository** を選択します。
3. 新しいリポジトリの所有者、名前、公開範囲を設定して作成します。
4. 作成したリポジトリを clone します。

```sh
git clone https://github.com/<owner>/<new-repository>.git
cd <new-repository>
code .
```

5. VS Code で `Dev Containers: Reopen in Container` を実行します。

### GitHub CLI から作る

GitHub CLI にログイン済みの場合は、次のコマンドでも作成できます。

```sh
gh repo create <owner>/<new-repository> \
	--template high-soar/dev-template \
	--private \
	--clone
```

公開リポジトリにする場合は `--private` を `--public` に変更します。作成後は生成されたディレクトリで `code .` を実行し、Dev Container を起動します。

## 日常の確認

依存関係を導入します。

```sh
npm install
```

コミット前またはプルリクエスト前に、次の品質チェックを実行します。

```sh
npm run format:check
npm run lint
npm test
npm run typecheck
```

整形が必要な場合は次を実行します。

```sh
npm run format
```

## Git フック

`npm install` または `npm ci` を実行すると、リポジトリ管理下の [`.githooks/pre-push`](.githooks/pre-push) がこの clone の Git 設定に登録されます。以降の `git push` では、push 前に `npm run lint` が実行されます。

既存の clone で再設定する場合は次を実行します。

```sh
npm run prepare
```

プルリクエストと `main` への push では、同じチェックが GitHub Actions により実行されます。

## テンプレート利用時の作業

1. `package.json` の `name`、`description`、`version` をプロジェクトに合わせて変更します。
2. アプリケーションの依存関係とソースコードを追加します。
3. TypeScript を使う場合は、プロジェクトに必要な `tsconfig.json` を追加します。型検査は設定ファイルを優先し、未作成の場合はリポジトリ中の TypeScript ファイルを検査します。
4. 必要な環境変数を `.env.example` に記載し、実値を Git に追加しないようにします。

共通の AI 向けルールは [AGENTS.md](AGENTS.md) が正本です。Copilot と Google Antigravity の設定は、そこから参照する構成にしています。
