# 开源仓库托管策略（国内 + 国际）

## 目标

**同一时刻、同一提交**发布到两个平台，避免"国内先发、国际后补"造成仓库漂移。

| 平台 | 仓库 | 定位 |
|---|---|---|
| Gitee（国内） | `yin-kang83/docgraph-kb-public` | 国内访问快、备案合规口径 |
| GitHub（国际） | `yin-kang83/docgraph-kb-public` | 国际曝光、Issues/PR 协作 |

> 本仓库为**脱敏公开版**，不含真实判例/客户数据/PII；示例为合成数据。
> 原私有仓 `docgraph-kb` 保留，不直接转 public。

## 分支约定

```text
opensource  本地清理/发布分支（唯一对外分支）
main        远端默认分支（Gitee 与 GitHub 同名）
```

本地 `opensource` 推送为两边 `main`，保持提交哈希一致。

## 发布前检查（每次都走）

```text
1 git status / git diff --stat        确认只含预期改动
2 敏感文件扫描：*.db *.zip *.key *.token *.pem .env
3 大文件检查：单文件 > 50MB 拒绝
4 无本机绝对路径（盘符路径 / 用户目录）
5 pytest 全绿
6 LICENSE / README 边界声明存在
7 双推后 ls-remote 两平台提交哈希一致
```

## 同步方式

```powershell
# 一次性配置（GitHub 地址 + PAT）
.\sync-mirrors.ps1 -GithubUrl https://github.com/<user>/docgraph-kb.git -GithubToken <PAT>

# 日常
.\sync-mirrors.ps1
```

## 不随仓库分发

数据（判例/法条库、原始 ZIP）、`raw_rows`/`rejects`（个人信息）、密钥、内部决策文档。
详见 `docs/PUBLIC_SCOPE.md`。
