import secrets

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Contest, Course, Enrollment, Submission, User

from ..deps import CurrentUser, Session
from ..schemas import CourseIn, CourseOut, Dashboard, DashboardStudent, JoinIn
from .contests import new_code

router = APIRouter(prefix="/courses", tags=["courses"])


def teaches(course: Course, user: User) -> bool:
    return user.role == "admin" or course.instructor_id == user.id


async def _outs(session: AsyncSession, courses: list[Course], user: User) -> list[CourseOut]:
    """Courses as the viewer sees them, with two queries however many there are."""
    ids = [c.id for c in courses]
    students = {k: v for k, v in await session.execute(
        select(Enrollment.course_id, func.count()).where(Enrollment.course_id.in_(ids))
        .group_by(Enrollment.course_id))}
    names = {k: v for k, v in await session.execute(select(User.id, User.name).where(
        User.id.in_({c.instructor_id for c in courses})))}
    return [CourseOut(id=c.id, title=c.title, description=c.description,
                      instructor=names.get(c.instructor_id, ""), students=students.get(c.id, 0),
                      teaches=teaches(c, user),
                      invite_code=c.invite_code if teaches(c, user) else None)
            for c in courses]


async def _out(session: AsyncSession, course: Course, user: User) -> CourseOut:
    return (await _outs(session, [course], user))[0]


async def teaching(session: AsyncSession, course_id: int, user: User) -> Course:
    course = await session.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "Course not found")
    if not teaches(course, user):
        raise HTTPException(403, "Only the instructor can see this")
    return course


@router.post("", response_model=CourseOut, status_code=201)
async def create(body: CourseIn, user: CurrentUser, session: Session) -> CourseOut:
    if user.role not in ("instructor", "admin"):
        raise HTTPException(403, "Only instructors and admins can create courses")
    course = Course(title=body.title.strip(), description=body.description.strip(),
                    instructor_id=user.id, invite_code=new_code())
    session.add(course)
    await session.commit()
    return await _out(session, course, user)


@router.get("", response_model=list[CourseOut])
async def my_courses(user: CurrentUser, session: Session) -> list[CourseOut]:
    """Courses the user teaches or is enrolled in."""
    enrolled = select(Enrollment.course_id).where(Enrollment.user_id == user.id)
    courses = await session.scalars(
        select(Course).where((Course.instructor_id == user.id) | Course.id.in_(enrolled))
        .order_by(Course.id.desc()))
    return await _outs(session, list(courses), user)


@router.post("/join", response_model=CourseOut)
async def join(body: JoinIn, user: CurrentUser, session: Session) -> CourseOut:
    code = body.code.strip()
    course = await session.scalar(select(Course).where(Course.invite_code == code))
    if course is None or not secrets.compare_digest(code, course.invite_code):
        raise HTTPException(404, "No course has this invite code")
    await session.execute(insert(Enrollment).values(course_id=course.id, user_id=user.id)
                          .on_conflict_do_nothing())
    await session.commit()
    return await _out(session, course, user)


@router.get("/{course_id}/dashboard", response_model=Dashboard)
async def dashboard(course_id: int, user: CurrentUser, session: Session) -> Dashboard:
    """For the instructor: every enrolled student's best score on each task of the
    course's contests, with submission counts and last activity."""
    course = await teaching(session, course_id, user)
    contests = list(await session.scalars(
        select(Contest).where(Contest.course_id == course.id).order_by(Contest.id)))
    students = list(await session.scalars(
        select(User).join(Enrollment, Enrollment.user_id == User.id)
        .where(Enrollment.course_id == course.id).order_by(User.name)))
    rows = await session.execute(
        select(Submission.user_id, Submission.contest_id, Submission.problem_id, Submission.dim,
               func.max(Submission.score), func.count(), func.max(Submission.created_at))
        .where(Submission.contest_id.in_([c.id for c in contests]))
        .group_by(Submission.user_id, Submission.contest_id, Submission.problem_id,
                  Submission.dim))
    per: dict[int, DashboardStudent] = {
        s.id: DashboardStudent(user_id=s.id, name=s.name, email=s.email, scores={},
                               submissions=0, last_active=None) for s in students}
    for user_id, contest_id, problem_id, dim, best, count, last in rows:
        if (student := per.get(user_id)) is None:
            continue
        student.scores[f"{contest_id}:{problem_id}@{dim}"] = best
        student.submissions += count
        student.last_active = max(filter(None, [student.last_active, last]))
    return Dashboard(
        course=await _out(session, course, user),
        columns=[{"key": f"{c.id}:{t['problem_id']}@{t['dim']}", "contest": c.title,
                  "contest_id": c.id, "problem_id": t["problem_id"], "dim": t["dim"]}
                 for c in contests for t in c.tasks],
        students=list(per.values()))
