# -*- coding: utf-8 -*-
# wechat-like-cv-server.py - 视觉计算中心（添加调试信息）
import uvicorn
import cv2
import numpy as np
import time
import logging
from fastapi import FastAPI, File, UploadFile, Form

# 日志配置（更详细）
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - [SERVER] - %(levelname)s - %(message)s')
logger = logging.getLogger("VisionServer")

app = FastAPI()
sift_engine = cv2.SIFT_create()
# FLANN 参数：使用 KD-Tree 索引加速
index_params = dict(algorithm=1, trees=5)
search_params = dict(checks=50)
flann_matcher = cv2.FlannBasedMatcher(index_params, search_params)

def algorithm_sift(template_img, target_img):
    """SIFT 特征匹配，返回中心坐标和外接矩形"""
    t0 = time.time()
    logger.debug("开始 SIFT 匹配...")
    
    # 1. 检测特征点
    kp1, des1 = sift_engine.detectAndCompute(template_img, None)
    kp2, des2 = sift_engine.detectAndCompute(target_img, None)
    
    if des1 is None or des2 is None or len(kp1) < 5:
        logger.warning("特征点不足，无法匹配")
        return None
    
    # 2. KNN 匹配
    matches = flann_matcher.knnMatch(des1, des2, k=2)
    good_matches = [m for m, n in matches if m.distance < 0.75 * n.distance]
    logger.debug(f"好匹配点数: {len(good_matches)}")
    
    # 3. 单应性矩阵计算 (至少6个点)
    if len(good_matches) >= 6:
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        
        if M is not None:
            h, w = template_img.shape
            pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
            dst = cv2.perspectiveTransform(pts, M)
            
            x_coords = dst[:, 0, 0]
            y_coords = dst[:, 0, 1]
            
            # 计算外接矩形
            rect = [int(min(x_coords)), int(min(y_coords)), int(max(x_coords)), int(max(y_coords))]
            cx = int(np.mean(x_coords))
            cy = int(np.mean(y_coords))
            
            logger.info(f"SIFT 匹配成功 | 耗时: {(time.time()-t0)*1000:.1f}ms | 位置: ({cx}, {cy})")
            return {"pos": [cx, cy], "rect": rect}
            
    logger.warning("单应性矩阵计算失败")
    return None

@app.post("/vision/process")
async def process_image(
    mode: str = Form(...), 
    target: UploadFile = File(...), 
    template: UploadFile = File(None)
):
    logger.info(f"接收到 HTTP 请求 | 模式: {mode}")
    try:
        # 读取上传图片
        target_bytes = await target.read()
        img_target = cv2.imdecode(np.frombuffer(target_bytes, np.uint8), cv2.IMREAD_COLOR)
        img_target_gray = cv2.cvtColor(img_target, cv2.COLOR_BGR2GRAY)
        logger.debug(f"目标图像尺寸: {img_target.shape}")
        
        result = {"success": False}
        
        if mode == 'sift' and template:
            tpl_bytes = await template.read()
            img_tpl = cv2.imdecode(np.frombuffer(tpl_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
            logger.debug(f"模板图像尺寸: {img_tpl.shape}")
            
            data = algorithm_sift(img_tpl, img_target_gray)
            if data:
                result = {"success": True, "data": data}
                logger.info("处理成功，返回结果")
            else:
                logger.warning("SIFT 匹配失败")
                
        return result
    except Exception as e:
        logger.error(f"处理错误: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    logger.info("🚀 启动视觉服务器...")
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="debug")
    logger.info("服务器运行中...")