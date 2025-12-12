from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

PROFILE_COOKIE_NAME = "decade_journey_profile"

@router.get("/logout")
def logout():
    response = RedirectResponse("/select-profile", status_code=303)
    response.delete_cookie(PROFILE_COOKIE_NAME)
    return response

@router.get("/select-profile", response_class=HTMLResponse)
def select_profile_page(request: Request):
    return templates.TemplateResponse("select_profile.html", {"request": request})

@router.post("/set-profile/{name}")
def set_profile(name: str):
    response = RedirectResponse("/", status_code=303)
    # Profile Cookie (1 Year)
    response.set_cookie(key=PROFILE_COOKIE_NAME, value=name, httponly=True, max_age=60*60*24*365)
    return response
