# WeChat Moments Auto-Liker Pro 🚀✨

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?logo=opensourceinitiative)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/throokie/pyquan-like?style=for-the-badge&color=yellow&logo=github)](https://github.com/throokie/pyquan-like/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/throokie/pyquan-like?style=for-the-badge&color=teal&logo=github)](https://github.com/throokie/pyquan-like/network/members)
[![GitHub issues](https://img.shields.io/github/issues/throokie/pyquan-like?style=for-the-badge&color=red&logo=github)](https://github.com/throokie/pyquan-like/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/throokie/pyquan-like?style=for-the-badge&color=purple&logo=github)](https://github.com/throokie/pyquan-like/pulls)
[![Last Commit](https://img.shields.io/github/last-commit/throokie/pyquan-like?style=for-the-badge&logo=git&logoColor=white&color=green)](https://github.com/throokie/pyquan-like/commits/main)
[![Contributors](https://img.shields.io/github/contributors/throokie/pyquan-like?style=for-the-badge&color=brightgreen&logo=github)](https://github.com/throokie/pyquan-like/graphs/contributors)
[![Code Size](https://img.shields.io/github/languages/code-size/throokie/pyquan-like?style=for-the-badge&logo=python&color=blueviolet)](https://github.com/throokie/pyquan-like)
[![Top Language](https://img.shields.io/github/languages/top/throokie/pyquan-like?style=for-the-badge&logo=python&color=ff69b4)](https://github.com/throokie/pyquan-like)
[![CI Status](https://img.shields.io/github/actions/workflow/status/throokie/pyquan-like/ci.yml?branch=main&style=for-the-badge&logo=github&label=CI)](https://github.com/throokie/pyquan-like/actions)
[![CodeQL Security](https://img.shields.io/github/workflow/status/throokie/pyquan-like/CodeQL?style=for-the-badge&logo=github&label=CodeQL)](https://github.com/throokie/pyquan-like/security/code-scanning)
[![Open Source Love](https://badges.frapsoft.com/os/v1/open-source.svg?v=103&style=for-the-badge)](https://github.com/ellerbrock/open-source-badges/)
[![Made with ❤️ in China](https://img.shields.io/badge/Made%20with%20❤️%20in-China-ff69b4.svg?style=for-the-badge)](https://github.com/throokie/pyquan-like)

**WeChat Moments Auto-Liker Pro** 是基于 OpenCV 模板匹配的朋友圈空心赞辅助实验项目（研究/自用向），不保证全机型可用。

演示需本地运行；占位图已移除。

## 已知限制

- 分辨率、主题或微信版本变化会导致模板失效，需要按实际界面调整模板。
- 自动化操作可能违反平台规范，请自行评估使用风险。
- 提问请附系统版本、微信版本、日志和截图，以便定位问题。

## 徽章墙（实时统计）

| 类别             | 徽章                                                                 | 说明                          |
|------------------|----------------------------------------------------------------------|-------------------------------|
| 项目活跃度       | [![Stars](https://img.shields.io/github/stars/throokie/pyquan-like?style=for-the-badge&logo=github&color=yellow)](https://github.com/throokie/pyquan-like/stargazers) | 当前星标数（实时）            |
| 社区贡献         | [![Contributors](https://img.shields.io/github/contributors/throokie/pyquan-like?style=for-the-badge&color=brightgreen&logo=github)](https://github.com/throokie/pyquan-like/graphs/contributors) | 贡献者数量                    |
| 代码质量         | [![CodeQL](https://img.shields.io/github/workflow/status/throokie/pyquan-like/CodeQL?style=for-the-badge&logo=github&label=CodeQL)](https://github.com/throokie/pyquan-like/security/code-scanning) | 安全扫描状态              |
| 构建状态         | [![CI](https://img.shields.io/github/actions/workflow/status/throokie/pyquan-like/ci.yml?branch=main&style=for-the-badge&logo=github&label=CI)](https://github.com/throokie/pyquan-like/actions) | CI/CD 持续集成                |
| 编程语言         | [![Top Language](https://img.shields.io/github/languages/top/throokie/pyquan-like?style=for-the-badge&logo=python&color=ff69b4)](https://github.com/throokie/pyquan-like) | Python 占比最高               |
| 开源精神         | [![Open Source Love](https://badges.frapsoft.com/os/v1/open-source.svg?v=103&style=for-the-badge)](https://github.com/ellerbrock/open-source-badges/) | 我们热爱开源！                |

## 快速上手

```bash
# 1. 克隆项目
git clone https://github.com/throokie/pyquan-like.git
cd pyquan-like

# 2. 安装依赖
pip install -r requirements.txt

# 3. 仓库已附带模板图片，请按实际界面检查是否适用
#   two_dots_orig.png    → 朋友圈动态的“...”按钮
#   like_hollow_orig.png → 空心点赞图标

# 4. 启动
python client.py
```
