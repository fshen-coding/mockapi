# MockAPI Kubernetes 部署

## 本次部署

- 服务器：`47.107.112.226`，Alibaba Cloud Linux 3，单节点 K3s `v1.36.4+k3s1`。
- 入口：`https://mockapi.fshencoding.cn`。HTTP 自动跳转 HTTPS。
- 公网入口不再使用 Basic Auth 弹窗，访客可直接打开页面；应用内部仍按 MockAPI 账号和权限控制。
- 使用 Let’s Encrypt 为 `mockapi.fshencoding.cn` 签发证书，有效期至 2026-12-21。
- Certbot 使用 HTTP-01 challenge 自动续期；续期脚本会临时停止 gateway、更新 Kubernetes `gateway-tls` Secret 并恢复 gateway。
- 部署的是当前工作区代码，包括尚未提交的改动；没有创建分支或 commit。
- 原有本地 8000 服务及数据库未停止、未切换、未重建。

## 迁移范围与验证

迁移 MockAPI 自身 PostgreSQL 数据库及运行中应用的 `/app/web/data`。
没有迁移 SIT、UAT 等环境的外部业务 MySQL 数据库。

数据库一致性快照时间：**2026-09-22 19:46:08，北京时间**。
使用 PostgreSQL 导出快照，表记录数及内容摘要与 `pg_dump` 共用同一事务快照。
文件另行备份，不是与数据库原子一致的文件系统快照。

| 表 | 记录数 |
| --- | ---: |
| app_users | 44 |
| company_image_templates | 6 |
| contact_issues | 2 |
| prompt_templates | 20 |
| scenario_meta_overrides | 2 |
| scenario_step_meta_overrides | 5 |
| scenario_step_order_overrides | 2 |
| scenario_step_overrides | 105 |
| user_operations | 25878 |
| user_sessions | 4948 |

上线前验证了 10 张表的记录数和内容摘要，以及 39 个数据文件的 SHA-256，全部匹配。
数据库和应用容器分别重建后，再次确认账号、操作记录和会话记录数保持不变。
公网验证：HTTP 301、未认证 HTTPS 401、认证后健康检查/首页/JS/CSS 均为 200；Let’s Encrypt 证书链验证通过。
浏览器验证：登录页面正常显示，无页面 JavaScript 异常。
数据库 5432、应用 8000、集群管理 6443 均不能从测试客户端直接访问。

本地与服务器现在是两套独立数据；快照之后本地新增内容不会自动同步到服务器。
开始正式使用新入口后，应避免两边同时写入。若需再次切换数据，先安排停止写入窗口，
备份两端，再另行处理增量或重新导入；不要直接在已使用的新库上重复恢复本次备份。

## 外部业务数据库连通性

| 环境 | 原本地容器 | 新服务器 | 说明 |
| --- | --- | --- | --- |
| UAT | 成功 | 成功 | 只执行了 `SELECT 1` |
| DEV | 成功 | 成功 | 只执行了 `SELECT 1` |
| SIT | 成功 | TCP 超时 | 需检查目标数据库安全组/白名单，端口 3306 |
| PREPROD | 成功 | TCP 超时 | 需检查目标数据库安全组/白名单，端口 3306 |
| REG | 成功 | TCP 超时 | 需检查目标数据库安全组/白名单，端口 3307 |
| LOCAL | 失败 | 失败 | 原有 LOCAL 数据库连接本来就不可用 |

对于超时的环境，请由数据库管理员确认是否允许服务器出口 `47.107.112.226/32`。
当前只有网络超时证据，尚不能断言一定是白名单问题。
没有修改外部数据库，也没有触发注册、放款、还款等业务操作。
AI 模型、全部业务 webhook 和浏览器自动化端到端流程未执行。

## 服务器结构

- Kubernetes namespace：`mockapi`。
- `StatefulSet/postgres`：PostgreSQL 16，ClusterIP，不对公网暴露。
- `Deployment/mockapi`：单副本，镜像 `mockapi:20260922`，关闭自动 reload。
- `Deployment/gateway`：Nginx，80/443 端口，TLS、独立密码保护、WebSocket 转发。
- 数据库与附件分别使用 PVC，PV 回收策略已设为 `Retain`。
- Secret 启用 K3s 静态加密；环境变量配置通过 Secret 注入，`.env` 和运行数据不写入本次镜像；源代码中的原有配置未重构。
- K3s 及防火墙开机自启；`mockapi-control-plane-firewall.service` 阻止外网访问管理端口。
- 系统启用了 cgroup v2，原启动配置备份保存在 `/opt/mockapi-deploy/grub.before-cgroup2`。
- 部署文件在 `/opt/mockapi-deploy`，迁移备份与校验报告在 `/opt/mockapi-backups`。

这是单节点部署，不是高可用集群。PVC 使用本机磁盘，不能抵御服务器或磁盘整体故障；
迁移备份同时保留在本地，但没有配置持续异地备份。
`local-path` PVC 标注的 5Gi 不代表文件系统自动实施了 5Gi 硬配额，应监控实际磁盘空间。

## 常用维护命令

以下命令在服务器执行：

```sh
kubectl -n mockapi get pods,pvc
kubectl -n mockapi logs deployment/mockapi --tail=100
kubectl -n mockapi logs postgres-0 --tail=100
kubectl -n mockapi rollout restart deployment/mockapi
kubectl -n mockapi rollout status deployment/mockapi
```

手动备份数据库：

```sh
umask 077
kubectl -n mockapi exec postgres-0 -- pg_dump -U mockapi -d mockapi -Fc --no-owner --no-acl > "/opt/mockapi-backups/mockapi-$(date +%Y%m%d-%H%M%S).dump"
```

`deploy/k8s/Dockerfile` 会在镜像构建阶段执行前端构建。从项目根目录手工构建时运行：

```sh
docker build -f deploy/k8s/Dockerfile -t mockapi:<新的版本号> .
```

导出并传输镜像到服务器后，用 `k3s ctr images import --platform linux/amd64 <镜像归档>`
导入，更新 Deployment 的镜像标签并检查 rollout。不要覆盖正在使用的同名标签。
`seed-data.yaml` 和 `verify-migration.yaml` 是本次一次性迁移任务，不应作为日常部署重复执行。

## GitHub Actions CI/CD

工作流位于 `.github/workflows/ci-cd.yml`：

- Pull Request：构建前端并编译检查 Python 源码，不推送镜像。
- 推送 `main`：执行检查，构建 `linux/amd64` 镜像，并推送 `main` 和不可变的 `sha-<完整 commit SHA>` 标签到 GHCR。
- 在 GitHub Actions 中从 `main` 手工运行工作流：重新构建镜像，经 `production` Environment 后发布该 SHA 镜像。
- 发布脚本只接受 `ghcr.io/fshen1999/mockapi:sha-<40位 SHA>`，等待 Deployment 就绪；失败时恢复发布前的镜像。

Kubernetes namespace 中必须存在 `ghcr-pull`：

```sh
kubectl -n mockapi get secret ghcr-pull
kubectl -n mockapi get deployment mockapi \
  -o jsonpath='imagePullSecrets={.spec.template.spec.imagePullSecrets[*].name}{"\n"}'
```

首次接入服务器时，将受限发布脚本安装到固定路径：

```sh
install -d -m 0755 /opt/mockapi-deploy
install -m 0755 deploy-image.sh /opt/mockapi-deploy/deploy-image.sh
install -m 0755 ci-ssh-entrypoint.sh /opt/mockapi-deploy/ci-ssh-entrypoint.sh
```

为 GitHub Actions 单独生成一把 Ed25519 key。服务器端只把公钥加入 `/root/.ssh/authorized_keys`，并在公钥前添加强制命令和 SSH 限制：

```text
restrict,command="/opt/mockapi-deploy/ci-ssh-entrypoint.sh" ssh-ed25519 AAAA... github-actions-mockapi
```

该 key 无法获得交互式 shell，且入口脚本只接受 `deploy-mockapi <受信 GHCR SHA 镜像>`。GitHub 仓库的 `production` Environment 需要配置以下 Secrets：

| Secret | 内容 |
| --- | --- |
| `DEPLOY_HOST` | 服务器域名或 IP |
| `DEPLOY_USER` | `root`（该 key 已由 forced command 限制） |
| `DEPLOY_SSH_KEY` | 单独生成的 Ed25519 私钥全文 |
| `DEPLOY_KNOWN_HOSTS` | 已核验的服务器 SSH host key 行 |

建议为 `production` Environment 配置 required reviewers。若当前 GitHub 套餐不支持 required reviewers，`workflow_dispatch` 本身仍保留手工发布步骤。

原应用有部分仅基于用户名判断角色的接口，本次没有改变其业务鉴权逻辑。
公网入口取消了 Basic Auth；正式扩大开放范围前，应确认应用内部登录、权限校验和接口限流满足 To C 使用要求。
