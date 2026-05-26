import os
import uuid
import asyncio
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

from services.kakao_service import search_restaurant
from services.claude_service import analyze_photos, generate_blog_post
from services.tistory_service import post_to_tistory
from services.image_service import save_and_resize, cleanup_uploads

app = FastAPI(title="티스토리 맛집 블로그 자동화")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")

scheduler = AsyncIOScheduler()
# 예약 발행 상태 추적 (메모리 저장, 재시작 시 초기화)
scheduled_jobs: Dict[str, dict] = {}


@app.on_event("startup")
async def startup():
    Path("uploads").mkdir(exist_ok=True)
    scheduler.start()


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/search-restaurant")
async def search(query: str = Form(...)):
    try:
        result = await search_restaurant(query)
        return JSONResponse(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"검색 오류: {str(e)}")


@app.post("/generate")
async def generate(
    restaurant_name: str = Form(...),
    restaurant_address: str = Form(""),
    restaurant_phone: str = Form(""),
    restaurant_category: str = Form(""),
    restaurant_url: str = Form(""),
    visit_date: str = Form(""),
    extra_notes: str = Form(""),
    images: List[UploadFile] = File(default=[]),
):
    image_paths = []
    try:
        # 이미지 저장 및 리사이즈
        for img in images:
            if img.filename and img.size and img.size > 0:
                file_bytes = await img.read()
                path = save_and_resize(file_bytes, img.filename)
                image_paths.append(path)

        restaurant = {
            "name": restaurant_name,
            "address": restaurant_address,
            "phone": restaurant_phone,
            "category": restaurant_category,
            "url": restaurant_url,
        }

        # 사진 분석
        photo_analysis = ""
        if image_paths:
            photo_analysis = await analyze_photos(image_paths)

        # 블로그 글 생성
        post_data = await generate_blog_post(
            restaurant=restaurant,
            photo_analysis=photo_analysis,
            visit_date=visit_date,
            extra_notes=extra_notes,
        )

        # 이미지 경로 목록 반환 (웹에서 미리보기용)
        image_urls = [f"/uploads/{Path(p).name}" for p in image_paths]
        post_data["image_paths"] = image_paths
        post_data["image_urls"] = image_urls

        return JSONResponse(post_data)

    except Exception as e:
        cleanup_uploads(image_paths)
        raise HTTPException(status_code=500, detail=f"글 생성 오류: {str(e)}")


@app.post("/post")
async def post(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    content: str = Form(...),
    tags: str = Form(""),
    image_paths: str = Form(""),
    scheduled_at: str = Form(""),
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    path_list = [p.strip() for p in image_paths.split("|") if p.strip() and Path(p.strip()).exists()]
    schedule_time = scheduled_at.strip() if scheduled_at.strip() else None

    if schedule_time:
        # 예약 발행: APScheduler로 등록
        job_id = uuid.uuid4().hex
        scheduled_jobs[job_id] = {
            "status": "scheduled",
            "title": title,
            "scheduled_at": schedule_time,
            "url": None,
            "error": None,
        }

        run_time = datetime.fromisoformat(schedule_time)
        scheduler.add_job(
            _do_post,
            "date",
            run_date=run_time,
            id=job_id,
            args=[job_id, title, content, tag_list, path_list],
        )
        return JSONResponse({"status": "scheduled", "job_id": job_id, "scheduled_at": schedule_time})
    else:
        # 즉시 발행: 백그라운드 태스크
        job_id = uuid.uuid4().hex
        scheduled_jobs[job_id] = {
            "status": "posting",
            "title": title,
            "scheduled_at": None,
            "url": None,
            "error": None,
        }
        background_tasks.add_task(_do_post, job_id, title, content, tag_list, path_list)
        return JSONResponse({"status": "posting", "job_id": job_id})


async def _do_post(job_id: str, title: str, content: str, tags: List[str], image_paths: List[str]):
    try:
        result = await post_to_tistory(
            title=title,
            content=content,
            tags=tags,
            image_paths=image_paths if image_paths else None,
            headless=False,
        )
        scheduled_jobs[job_id]["status"] = "done" if result["success"] else "error"
        scheduled_jobs[job_id]["url"] = result.get("url")
        scheduled_jobs[job_id]["error"] = result.get("error")
    except Exception as e:
        scheduled_jobs[job_id]["status"] = "error"
        scheduled_jobs[job_id]["error"] = str(e)
    finally:
        cleanup_uploads(image_paths)


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = scheduled_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return JSONResponse(job)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
