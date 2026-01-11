# -*- encoding=utf8 -*-
# client.py - 航天级自动控制端 (纯ADB版 + 强力聚类 + 多设备支持 + CV服务管理)
import os
import cv2
import time
import random
import requests
import numpy as np
import logging
import subprocess
import shlex
import threading
from typing import List, Tuple, Optional
from multiprocessing import Process

# ================= 0. 环境日志配置 =================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logger = logging.getLogger("Bot")

def run_server():
    import uvicorn
    from wechat_like_cv_server import app  # 假设你的 server 文件名为 wechat_like_cv_server.py
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info")
    
# ================= 1. 工业级配置 =================
class Config:
    SERVER_URL = "http://localhost:9000/vision/process"  # 默认本地
    
    SEEDS = {
        "dots": "two_dots_orig.png", 
        "like": "like_hollow_orig.png"
    }
    
    # --- 滑动策略 ---
    SWIPE_START_RANGE = (0.5, 0.6) 
    MIN_SWIPE_DIST_PCT = 0.10  # 减小最小距离，提高精确性
    MAX_SWIPE_DIST_PCT = 0.30  # 减小最大距离，避免滑过头
    
    # --- 区域阈值 ---
    TOP_DEAD_ZONE = 200      
    BOTTOM_SAFE_LINE = 0.85  
    
    BURST_LIMIT = 40          
    SKIP_PROBABILITY = 0.01   
    MATCH_THRESHOLD = 0.8     
    UI_CHANGE_DIFF = 10.0     
    POLL_INTERVAL = 0.05
    
    # [新增] 聚类去重距离 (像素平方)
    CLUSTER_DIST_SQ = 2500 
    
    # [新增] 滑动缓冲像素（防滑不足）
    SWIPE_BUFFER_PX = 20

    # ADB 相关配置
    ADB_PATH = "adb"  # 如果adb不在PATH中，改为绝对路径如 "C:/platform-tools/adb.exe"
    TEMP_SCREENSHOT = "/sdcard/bot_screenshot_temp.jpg"
    LOCAL_SCREENSHOT = "temp_screenshot.jpg"

    # CV 配置文件
    CV_CONFIG_FILE = "cv_config.json"

# ================= 2. ADB设备管理器 =================
class ADBManager:
    def __init__(self, device_id: str = None):
        self.device_id = device_id
        self.width = 0
        self.height = 0
        if device_id:
            self._get_device_resolution()

    def run_adb_command(self, cmd: str) -> Tuple[bool, str]:
        """执行ADB命令并返回结果"""
        try:
            # 构建完整命令
            full_cmd = f"{Config.ADB_PATH}"
            if self.device_id:
                full_cmd += f" -s {self.device_id}"
            full_cmd += f" {cmd}"
            
            # 执行命令
            result = subprocess.run(
                shlex.split(full_cmd),
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                logger.error(f"ADB命令执行失败 ({self.device_id}): {full_cmd}")
                logger.error(f"错误信息: {result.stderr}")
                return False, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"ADB命令超时 ({self.device_id}): {full_cmd}")
            return False, "Timeout"
        except Exception as e:
            logger.error(f"ADB命令执行异常 ({self.device_id}): {e}")
            return False, str(e)

    @staticmethod
    def list_devices() -> List[str]:
        """列出所有已连接的ADB设备"""
        try:
            result = subprocess.run(
                shlex.split(f"{Config.ADB_PATH} devices"),
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return []
            
            devices = []
            lines = result.stdout.splitlines()
            for line in lines[1:]:  # 跳过第一行标题
                if line.strip() and "device" in line and not "offline" in line:
                    device_id = line.split()[0].strip()
                    devices.append(device_id)
            
            return devices
        except Exception as e:
            logger.error(f"列出设备失败: {e}")
            return []

    def _get_device_resolution(self):
        """获取设备屏幕分辨率"""
        success, output = self.run_adb_command("shell wm size")
        if success and "Physical size:" in output:
            size_str = output.split("Physical size:")[1].strip()
            width, height = map(int, size_str.split("x"))
            self.width = width
            self.height = height
            logger.info(f"📏 设备 {self.device_id} 分辨率: {width}x{height}")
        else:
            # 默认分辨率
            self.width = 1080
            self.height = 2400
            logger.warning(f"⚠️ 设备 {self.device_id} 获取分辨率失败，使用默认值: {self.width}x{self.height}")

    def screenshot(self) -> Optional[np.ndarray]:
        """获取屏幕截图并返回OpenCV格式的图像"""
        # 1. 在设备上截图
        self.run_adb_command(f"shell screencap -p {Config.TEMP_SCREENSHOT}")
        
        # 2. 拉取到本地（每个设备用唯一文件名）
        local_path = f"temp_screenshot_{self.device_id}.jpg" if self.device_id else Config.LOCAL_SCREENSHOT
        success, _ = self.run_adb_command(f"pull {Config.TEMP_SCREENSHOT} {local_path}")
        if not success:
            logger.error(f"❌ 设备 {self.device_id} 拉取截图失败")
            return None
        
        # 3. 读取并返回
        img = cv2.imread(local_path)
        if img is None:
            logger.error(f"❌ 设备 {self.device_id} 读取截图失败")
            return None
        
        return img

    def touch(self, x: int, y: int):
        """模拟触摸操作"""
        # 添加随机偏移，更接近真人操作
        x += random.randint(-2, 2)
        y += random.randint(-2, 2)
        self.run_adb_command(f"shell input tap {x} {y}")

    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.8):
        """模拟滑动操作"""
        # duration单位：秒 -> 转换为ADB需要的毫秒
        duration_ms = int(duration * 1000)
        self.run_adb_command(f"shell input swipe {start_x} {start_y} {end_x} {end_y} {duration_ms}")

# ================= 3. 视觉闭环系统 =================
class VisualServo:
    def __init__(self, adb_manager: ADBManager):
        self.session = requests.Session()
        self.adb_manager = adb_manager
    
    def get_screen_cv(self):
        return self.adb_manager.screenshot()

    def find_all_buttons(self, screen, template):
        """
        [修复版] 寻找并聚类所有按钮，强制转换为原生 int 类型
        """
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        gray_tpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        h, w = gray_tpl.shape[:2]
        
        # 1. 模板匹配
        res = cv2.matchTemplate(gray_screen, gray_tpl, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= Config.MATCH_THRESHOLD)
        
        # 将 numpy 数组转为坐标列表 [(x, y), ...]
        raw_points = list(zip(*loc[::-1])) 
        
        if not raw_points:
            return []

        # 2. 强力空间聚类 (去重)
        targets = []
        
        for pt in raw_points:
            # [关键修复]：必须在这里转为 Python 原生 int
            cx = int(pt[0] + w//2)
            cy = int(pt[1] + h//2)
            
            is_new = True
            for t in targets:
                # 计算欧氏距离的平方
                dist_sq = (cx - t[0])**2 + (cy - t[1])**2
                if dist_sq < Config.CLUSTER_DIST_SQ:
                    is_new = False
                    break
            
            if is_new:
                targets.append((cx, cy))
        
        # 3. 按 Y 坐标排序 (从上到下)
        targets.sort(key=lambda p: p[1])
        
        if targets:
            log_str = " | ".join([f"Y={t[1]}" for t in targets])
            logger.info(f"🔎 [{self.adb_manager.device_id}] 发现 {len(targets)} 个独立目标: [{log_str}]")
            
        return targets

    def multiscale_match(self, screen, template_path):
        if not os.path.exists(template_path): return None
        tpl = cv2.imread(template_path)
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        gray_tpl = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
        tH, tW = gray_tpl.shape[:2]
        best = None
        for scale in np.linspace(0.8, 1.2, 5):
            resized = cv2.resize(gray_tpl, (int(tW * scale), int(tH * scale)))
            if gray_screen.shape[0] < resized.shape[0] or gray_screen.shape[1] < resized.shape[1]: continue
            res = cv2.matchTemplate(gray_screen, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > (best[0] if best else 0.65):
                best = (max_val, max_loc, resized.shape[:2])
        if best:
            v, loc, (h, w) = best
            # [关键修复] 这里的返回也强制转 int
            return {"pos": (int(loc[0]+w//2), int(loc[1]+h//2)), 
                    "rect": (int(loc[0]), int(loc[1]), int(loc[0]+w), int(loc[1]+h)), 
                    "conf": v}
        return None

    def call_sift_server(self, screen, tpl_key):
        try:
            tpl_path = Config.SEEDS[tpl_key]
            if not os.path.exists(tpl_path): return None
            _, img_enc = cv2.imencode('.jpg', screen)
            with open(tpl_path, 'rb') as f:
                files = {'target': ('t.jpg', img_enc.tobytes(), 'image/jpeg'),
                         'template': ('p.jpg', f.read(), 'image/jpeg')}
                resp = self.session.post(Config.SERVER_URL, data={'mode': 'sift'}, files=files, timeout=5)
                if resp.status_code == 200 and resp.json().get('success'):
                    # [关键修复] 确保服务端返回的数据也被转为 int
                    data = resp.json()['data']
                    data['pos'] = [int(p) for p in data['pos']]
                    data['rect'] = [int(p) for p in data['rect']]
                    return data
        except Exception as e:
            logger.error(f"[{self.adb_manager.device_id}] CV服务器调用失败: {e}")
        return None

    def wait_for_ui_change(self, roi_rect, original_img, timeout=1.5):
        x1, y1, x2, y2 = roi_rect
        original_roi = cv2.cvtColor(original_img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        start_time = time.time()
        max_diff = 0
        while time.time() - start_time < timeout:
            current_screen = self.adb_manager.screenshot()
            if current_screen is None:
                time.sleep(Config.POLL_INTERVAL)
                continue
                
            current_roi = cv2.cvtColor(current_screen[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
            diff = np.mean(cv2.absdiff(original_roi, current_roi))
            max_diff = max(max_diff, diff)
            if diff > Config.UI_CHANGE_DIFF: 
                logger.info(f"⚡ [{self.adb_manager.device_id}] UI闭环检测通过 (Diff: {diff:.1f})")
                return True
            time.sleep(Config.POLL_INTERVAL)
        logger.debug(f"⚠️ [{self.adb_manager.device_id}] UI闭环超时 (最大Diff: {max_diff:.1f})")
        return False

# ================= 4. 中央控制器 =================
class BotController:
    def __init__(self, device_id: str):
        self.adb_manager = ADBManager(device_id)
        self.width = self.adb_manager.width
        self.height = self.adb_manager.height
        self.safe_y_limit = int(self.height * Config.BOTTOM_SAFE_LINE)
        
        self.servo = VisualServo(self.adb_manager)
        self.runtime_assets = {}
        self.vector = None       
        self.action_count = 0
        self.last_cy = None  # [新增] 记录上一个处理的 Y 位置，用于优化距离计算

    def random_sleep(self, min_s, max_s):
        time.sleep(random.uniform(min_s, max_s))

    def calibrate(self):
        logger.info(f"🛠 [{self.adb_manager.device_id}] 正在校准...")
        screen = self.servo.get_screen_cv()
        if screen is None:
            logger.error(f"❌ [{self.adb_manager.device_id}] 无法获取屏幕截图")
            return False
            
        match = self.servo.multiscale_match(screen, Config.SEEDS["dots"])
        if not match: match = self.servo.call_sift_server(screen, "dots")
        
        if not match:
            logger.critical(f"❌ [{self.adb_manager.device_id}] 校准失败: 未找到按钮")
            return False
            
        d_pos, d_rect = match['pos'], match['rect']
        self.runtime_assets["dots"] = screen[d_rect[1]:d_rect[3], d_rect[0]:d_rect[2]]
        
        self.adb_manager.touch(*d_pos)
        time.sleep(1.0) 
        menu_screen = self.servo.get_screen_cv()
        
        if menu_screen is None:
            logger.error(f"❌ [{self.adb_manager.device_id}] 无法获取菜单屏幕截图")
            return False
            
        match_like = self.servo.multiscale_match(menu_screen, Config.SEEDS["like"])
        if not match_like: match_like = self.servo.call_sift_server(menu_screen, "like")
        
        if match_like:
            l_pos, l_rect = match_like['pos'], match_like['rect']
            self.runtime_assets["like"] = menu_screen[l_rect[1]:l_rect[3], l_rect[0]:l_rect[2]]
            self.vector = (l_pos[0] - d_pos[0], l_pos[1] - d_pos[1])
            logger.info(f"✅ [{self.adb_manager.device_id}] 校准成功 (Vector: {self.vector})")
            self.adb_manager.touch(*d_pos)
            self.random_sleep(0.5, 0.8)
            return True
        else:
            logger.critical(f"❌ [{self.adb_manager.device_id}] 校准失败: 未找到赞图标")
            self.adb_manager.touch(*d_pos) 
            return False

    def check_liked_status(self, screen, dot_pos):
        if not self.vector: return False
        lx, ly = dot_pos[0] + self.vector[0], dot_pos[1] + self.vector[1]
        y1, y2 = int(ly - 40), int(ly + 40)
        x1, x2 = int(lx - 40), int(lx + 40)
        roi = screen[max(0, y1):min(self.height, y2), max(0, x1):min(self.width, x2)]
        if roi.size == 0: return False
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([0, 150, 150]), np.array([10, 255, 255])) + \
               cv2.inRange(hsv, np.array([170, 150, 150]), np.array([180, 255, 255]))
        return cv2.countNonZero(mask) > 15

    def execute_pipeline(self):
        if not self.calibrate(): return
        logger.info(f"🚀 [{self.adb_manager.device_id}] 多目标优先流水线启动")
        
        while True:
            screen = self.servo.get_screen_cv()
            if screen is None:
                logger.error(f"❌ [{self.adb_manager.device_id}] 无法获取屏幕截图，重试中...")
                self.random_sleep(1.0, 1.5)
                continue
            
            # 查找所有按钮
            all_buttons = self.servo.find_all_buttons(screen, self.runtime_assets["dots"])
            
            # 过滤掉顶部死区内的
            valid_buttons = [b for b in all_buttons if b[1] > Config.TOP_DEAD_ZONE]
            
            if valid_buttons:
                # 永远取 Top 1
                dot_pos = valid_buttons[0] 
                cy = dot_pos[1]
                
                logger.info(f"🎯 [{self.adb_manager.device_id}] 锁定顶部目标 @ Y={cy}")

                if cy > self.safe_y_limit:
                    logger.warning(f"⚠️ [{self.adb_manager.device_id}] 目标触底，大幅回正")
                    self.adaptive_swipe(pixel_distance=int(self.height * 0.4))
                    self.last_cy = None  # 重置记录
                    continue

                self.process_target(dot_pos, screen)
                
                # [优化] 自适应滑动：基于当前处理的 cy 和下一个按钮的距离计算（实现一次处理一条）
                if len(valid_buttons) > 1:
                    next_cy = valid_buttons[1][1]
                    calc_dist = max(0, next_cy - cy) + Config.SWIPE_BUFFER_PX  # 按钮间实际距离 + 缓冲
                    logger.info(f"📐 [{self.adb_manager.device_id}] 实时计算滑动距离: {calc_dist} (基于当前Y={cy} 和下一个Y={next_cy})")
                else:
                    calc_dist = int(self.height * 0.25)  # 默认减小以加快
                    logger.info(f"📐 [{self.adb_manager.device_id}] 无下一个按钮，使用默认滑动距离: {calc_dist}")
                
                self.adaptive_swipe(pixel_distance=calc_dist)
                self.last_cy = cy  # 更新记录（备用，如果下次无下一个可用）
                
            else:
                logger.info(f"🔍 [{self.adb_manager.device_id}] 无有效目标，补进扫描...")
                calc_dist = int(self.height * 0.25)  # 默认减小
                self.adaptive_swipe(pixel_distance=calc_dist)
                self.last_cy = None
                self.random_sleep(0.6, 0.9)  # 减小睡眠时间，加快速度
            
            if self.action_count >= Config.BURST_LIMIT:
                logger.info(f"💤 [{self.adb_manager.device_id}] 冷却休息...")
                time.sleep(random.randint(40, 70))
                self.action_count = 0
                self.calibrate() 

    def process_target(self, dot_pos, current_screen):
        if random.random() < Config.SKIP_PROBABILITY:
            logger.info(f"🎲 [{self.adb_manager.device_id}] 随机跳过")
            return

        # 点击目标位置
        click_x = int(dot_pos[0] + random.randint(-2, 2))
        click_y = int(dot_pos[1] + random.randint(-2, 2))
        self.adb_manager.touch(click_x, click_y)
        
        self.random_sleep(0.3, 0.5)  # 减小睡眠，加快
        menu_screen = self.servo.get_screen_cv()
        
        if menu_screen is None:
            logger.error(f"❌ [{self.adb_manager.device_id}] 无法获取菜单屏幕截图，跳过处理")
            return
        
        if self.check_liked_status(menu_screen, dot_pos):
            logger.info(f"💖 [{self.adb_manager.device_id}] [状态] 已赞")
            return 
        else:
            # 计算点赞位置
            tx = int(dot_pos[0] + self.vector[0] + random.randint(-2, 2))
            ty = int(dot_pos[1] + self.vector[1] + random.randint(-2, 2))
            
            logger.info(f"🔥 [{self.adb_manager.device_id}] [动作] 点赞")
            watch_rect = (int(tx-30), int(ty-40), int(dot_pos[0]+30), int(dot_pos[1]+40))
            self.adb_manager.touch(tx, ty)
            self.action_count += 1
            self.servo.wait_for_ui_change(watch_rect, menu_screen, timeout=1.0)  # 减小超时，加快

    def adaptive_swipe(self, pixel_distance):
        dist_pct = pixel_distance / self.height
        real_dist_pct = max(Config.MIN_SWIPE_DIST_PCT, min(dist_pct, Config.MAX_SWIPE_DIST_PCT))
        
        center_x = self.width // 2
        start_x = int(random.gauss(center_x, 20)) 
        end_x = int(start_x + random.randint(-15, 15))
        
        min_start = Config.SWIPE_START_RANGE[0]
        max_start = Config.SWIPE_START_RANGE[1]
        start_y_pct = random.uniform(min_start, max_start)
        start_y = int(self.height * start_y_pct)
        
        end_y = int(start_y - (self.height * real_dist_pct))
        duration = random.uniform(0.5, 0.7)  # 减小持续时间，加快滑动
        
        self.adb_manager.swipe(start_x, start_y, end_x, end_y, duration)
        
        # [关键修复] 滑动后立即轻触停止惯性漂移（用结束点附近的安全位置）
        self.random_sleep(0.1, 0.2)  # 微小延迟等滑动完成，减小时间
        stop_touch_x = center_x + random.randint(-50, 50)  # 中央偏随机
        stop_touch_y = max(end_y, int(self.height * 0.4)) + random.randint(-20, 20)  # 确保在中部以上，避免底部导航
        logger.debug(f"🛑 [{self.adb_manager.device_id}] 停止漂移: 轻触 @ ({stop_touch_x}, {stop_touch_y})")
        self.adb_manager.touch(stop_touch_x, stop_touch_y)
        
        self.random_sleep(0.4, 0.7)  # 整体减小睡眠，加快循环

# ================= 5. CV 服务管理 =================
def manage_cv_server():
    use_local = input("\n是否自动启动本地 CV 服务器? (y/n): ").strip().lower() == 'y'
    
    if not use_local:
        return None

    logger.info("🚀 使用独立进程启动本地 CV 服务器...")
    p = Process(target=run_server, daemon=True)
    p.start()
    # 移除 time.sleep(0.5) 以避免阻塞
    logger.info(f"✅ CV 服务器进程启动 (PID: {p.pid})")
    return p

def select_and_configure_devices() -> List[Tuple[str, bool]]:
    """
    返回: [(device_id, run_bot: bool), ...]
    """
    devices = ADBManager.list_devices()
    if not devices:
        logger.critical("❌ 未找到任何已连接的ADB设备")
        return []

    logger.info("\n📱 可用设备列表:")
    for i, dev in enumerate(devices, 1):
        logger.info(f"   [{i}] {dev}")

    selected_ids = []
    choice = input("\n请选择要连接的设备编号 (逗号分隔, e.g. 1,3 或 all): ").strip()
    if choice.lower() == 'all':
        selected_ids = devices
    else:
        try:
            idxs = [int(x.strip())-1 for x in choice.split(',')]
            selected_ids = [devices[i] for i in idxs if 0 <= i < len(devices)]
        except:
            logger.warning("输入无效，将使用空列表")
            return []

    if not selected_ids:
        return []

    # 对每个选中的设备，询问是否运行 bot 主功能
    configured = []
    logger.info("\n接下来为每个设备选择运行模式：")
    for dev_id in selected_ids:
        run_bot = input(f"设备 {dev_id} 是否运行完整点赞自动化？(y/n): ").strip().lower() == 'y'
        configured.append((dev_id, run_bot))
        logger.info(f"  → {dev_id} : {'完整自动化' if run_bot else '仅连接（监控/调试）'}")

    return configured

if __name__ == "__main__":
    server_process = None
    selected_devices = []           # ← 在 try 外提前声明为空列表
    configured_devices = []         # 如果你用了 configured_devices，也提前声明

    try:
        # 1. 统一处理 CV 服务器
        server_process = manage_cv_server()

        # 2. 选择并配置设备
        configured_devices = select_and_configure_devices()
        if not configured_devices:
            raise Exception("无有效设备配置，程序退出")

        # 3. 提取 device_id 列表用于清理（或直接用 configured_devices）
        selected_devices = [dev_id for dev_id, _ in configured_devices]

        # 4. 启动线程...
        threads = []
        for device_id, should_run_bot in configured_devices:
            bot = BotController(device_id)
            
            if should_run_bot:
                logger.info(f"启动完整 bot 线程: {device_id}")
                t = threading.Thread(
                    target=bot.execute_pipeline,
                    name=f"Bot-{device_id}",
                    daemon=True
                )
            else:
                # 监控模式...
                def monitor_only():
                    logger.info(f"[{device_id}] 监控模式启动，仅截图不操作")
                    while True:
                        img = bot.servo.get_screen_cv()
                        if img is None:
                            continue
                        logger.debug(f"[{device_id}] 截图成功 {img.shape}")
                        time.sleep(5)
                t = threading.Thread(target=monitor_only, name=f"Monitor-{device_id}", daemon=True)

            t.start()
            threads.append(t)

        # 等待线程
        try:
            for t in threads:
                t.join()
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在优雅退出...")

    except Exception as e:
        logger.critical(f"程序异常退出: {e}")
    
    finally:
        # 安全清理（selected_devices 已提前声明）
        for device_id in selected_devices:  # 现在永远安全
            local_path = f"temp_screenshot_{device_id}.jpg"
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except:
                    pass
        
        if os.path.exists(Config.LOCAL_SCREENSHOT):
            try:
                os.remove(Config.LOCAL_SCREENSHOT)
            except:
                pass
        
        # 关闭 CV 服务器
        if server_process and server_process.is_alive():
            try:
                server_process.terminate()
                server_process.join(timeout=3)
            except:
                server_process.kill()
            logger.info("本地 CV 服务器已终止")