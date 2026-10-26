"""Storefront admin HTTP routes — authenticated, company-scoped management of
the public shop's content: categories (with imagery), product presentation
fields and gallery, hero slides, testimonials, FAQs, policies and settings.

Every write is audit-logged via `log_action`; every upload goes through
`save_file` with an image-only allowlist and generated server-side keys.
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.permissions import P_FILES_UPLOAD, P_STOREFRONT_MANAGE, P_STOREFRONT_VIEW
from app.db.unit_of_work import get_db
from app.modules.audit.service import log_action
from app.modules.catalog.models import Category, Product, ProductImage, PRODUCT_BADGES
from app.modules.identity.dependencies import CompanyCtx, guard
from app.modules.storefront import service as svc
from app.modules.storefront.models import (
    StorefrontFaq,
    StorefrontHeroSlide,
    StorefrontPolicy,
    StorefrontSettings,
    StorefrontTestimonial,
)
from app.shared.files import IMAGE_CONTENT_TYPES, delete_file, save_file

router = APIRouter(prefix="/storefront/admin")


def _money(value: Decimal | None, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if value < 0:
        raise BusinessRuleError("BAD_AMOUNT", f"{field_name} must be >= 0")
    return value


def _badge(value: str | None) -> str | None:
    if value is not None and value not in PRODUCT_BADGES:
        raise BusinessRuleError("BAD_BADGE", f"badge must be one of {sorted(PRODUCT_BADGES)}")
    return value


def _sections(value: list | None) -> list | None:
    if value is None:
        return None
    out = []
    for section in value:
        if not isinstance(section, dict) or not section.get("heading") or not section.get("body"):
            raise BusinessRuleError("BAD_POLICY_SECTION", "Each section needs a heading and body")
        out.append({"heading": str(section["heading"])[:200], "body": str(section["body"])})
    return out


def _category_row(session: Session, company_id: str, category_id: str) -> Category:
    row = session.get(Category, category_id)
    if row is None or row.company_id != company_id:
        raise NotFoundError("Category")
    return row


def _product_row(session: Session, company_id: str, product_id: str) -> Product:
    row = session.get(Product, product_id)
    if row is None or row.company_id != company_id:
        raise NotFoundError("Product")
    return row


def _category_out(row: Category) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "slug": row.slug,
        "blurb": row.blurb,
        "tone": row.tone,
        "parent_id": row.parent_id,
        "image_url": svc.media_url(row.company_id, row.image_file_id),
        "sort_order": row.sort_order,
        "is_active": row.is_active,
    }


def _image_out(row: ProductImage) -> dict:
    return {
        "id": row.id,
        "url": svc.media_url(row.company_id, row.file_id),
        "alt": row.alt,
        "sort_order": row.sort_order,
        "is_cover": None,  # filled by the caller
    }


# ---- categories ----
@router.get("/categories")
def list_categories(ctx: CompanyCtx = Depends(guard(P_STOREFRONT_VIEW)), session: Session = Depends(get_db)):
    rows = session.execute(
        select(Category).where(Category.company_id == ctx.company_id).order_by(Category.sort_order, Category.name)
    ).scalars().all()
    return [_category_out(row) for row in rows]


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None
    slug: str | None = Field(default=None, max_length=80)
    blurb: str | None = Field(default=None, max_length=300)
    tone: str | None = Field(default=None, max_length=16)
    sort_order: int = 0
    is_active: bool = True


class CategoryUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    parent_id: str | None = None
    slug: str | None = Field(default=None, max_length=80)
    blurb: str | None = Field(default=None, max_length=300)
    tone: str | None = Field(default=None, max_length=16)
    sort_order: int | None = None
    is_active: bool | None = None


@router.post("/categories", status_code=201)
def create_category(payload: CategoryIn, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db)):
    row = Category(
        company_id=ctx.company_id,
        name=payload.name,
        parent_id=payload.parent_id,
        slug=(payload.slug or None) and payload.slug.strip().lower(),
        blurb=payload.blurb,
        tone=payload.tone,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
        created_by=ctx.user.id,
    )
    session.add(row)
    session.flush()
    log_action(
        session, action="storefront.category.created", entity_type="category", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"name": row.name, "slug": row.slug},
    )
    return _category_out(row)


@router.patch("/categories/{category_id}")
def update_category(
    category_id: str, payload: CategoryUpdateIn,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db),
):
    row = _category_row(session, ctx.company_id, category_id)
    before = {"name": row.name, "slug": row.slug, "is_active": row.is_active}
    data = payload.model_dump(exclude_unset=True)
    for field in ("name", "parent_id", "blurb", "tone", "sort_order", "is_active"):
        if field in data:
            setattr(row, field, data[field])
    if "slug" in data:
        row.slug = (data["slug"] or None) and data["slug"].strip().lower()
    session.flush()
    log_action(
        session, action="storefront.category.updated", entity_type="category", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, before_data=before,
    )
    return _category_out(row)


@router.post("/categories/{category_id}/image")
def upload_category_image(
    category_id: str, file: UploadFile,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE, P_FILES_UPLOAD)),
    session: Session = Depends(get_db),
):
    row = _category_row(session, ctx.company_id, category_id)
    record = save_file(
        session, file, company_id=ctx.company_id, purpose="category_image",
        created_by=ctx.user.id, allowed_types=IMAGE_CONTENT_TYPES, visibility="public",
    )
    row.image_file_id = record.id
    session.flush()
    log_action(
        session, action="storefront.category.image_uploaded", entity_type="category", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"file_id": record.id},
    )
    return {"category_id": row.id, "file_id": record.id, "image_url": svc.media_url(row.company_id, record.id)}


# ---- product presentation + gallery ----
class ProductContentIn(BaseModel):
    compare_at_price: Decimal | None = None
    badge: str | None = None
    highlights: list[str] | None = None
    colors: list[str] | None = None
    rating_avg: Decimal | None = Field(default=None, ge=0, le=5)
    rating_count: int | None = Field(default=None, ge=0)
    tone: str | None = Field(default=None, max_length=16)
    slug: str | None = Field(default=None, max_length=80)


@router.patch("/products/{product_id}")
def update_product_content(
    product_id: str, payload: ProductContentIn,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db),
):
    row = _product_row(session, ctx.company_id, product_id)
    data = payload.model_dump(exclude_unset=True)
    before = {"badge": row.badge, "compare_at_price": str(row.compare_at_price) if row.compare_at_price is not None else None}
    if "compare_at_price" in data:
        row.compare_at_price = _money(data["compare_at_price"], "compare_at_price")
    if "badge" in data:
        row.badge = _badge(data["badge"])
    for field in ("highlights", "colors", "rating_avg", "rating_count", "tone"):
        if field in data:
            setattr(row, field, data[field])
    if "slug" in data:
        row.slug = (data["slug"] or None) and data["slug"].strip().lower()
    session.flush()
    log_action(
        session, action="storefront.product.updated", entity_type="product", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, before_data=before,
    )
    return svc.product_detail(session, ctx.company_id, row.id, count_view=False)


@router.get("/products/{product_id}/images")
def list_product_images(
    product_id: str, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_VIEW)), session: Session = Depends(get_db),
):
    product = _product_row(session, ctx.company_id, product_id)
    rows = session.execute(
        select(ProductImage).where(ProductImage.product_id == product.id).order_by(ProductImage.sort_order, ProductImage.created_at)
    ).scalars().all()
    return [{**_image_out(row), "is_cover": row.file_id == product.image_file_id} for row in rows]


@router.post("/products/{product_id}/images", status_code=201)
def upload_product_image(
    product_id: str, file: UploadFile, alt: str | None = None, is_cover: bool = True,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE, P_FILES_UPLOAD)),
    session: Session = Depends(get_db),
):
    product = _product_row(session, ctx.company_id, product_id)
    record = save_file(
        session, file, company_id=ctx.company_id, purpose="product_image",
        created_by=ctx.user.id, allowed_types=IMAGE_CONTENT_TYPES, visibility="public",
    )
    last_sort = session.scalar(
        select(ProductImage.sort_order).where(ProductImage.product_id == product.id).order_by(ProductImage.sort_order.desc()).limit(1)
    ) or 0
    row = ProductImage(
        company_id=ctx.company_id, product_id=product.id, file_id=record.id,
        sort_order=last_sort + 1, alt=alt, created_by=ctx.user.id,
    )
    session.add(row)
    if is_cover or not product.image_file_id:
        product.image_file_id = record.id
    session.flush()
    log_action(
        session, action="storefront.product.image_uploaded", entity_type="product", entity_id=product.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"file_id": record.id},
    )
    return {**_image_out(row), "is_cover": row.file_id == product.image_file_id}


class GalleryOrderIn(BaseModel):
    order: list[str] = Field(min_length=1)


@router.put("/products/{product_id}/images")
def reorder_product_images(
    product_id: str, payload: GalleryOrderIn,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db),
):
    product = _product_row(session, ctx.company_id, product_id)
    rows = {
        row.id: row
        for row in session.execute(
            select(ProductImage).where(ProductImage.product_id == product.id)
        ).scalars().all()
    }
    if set(payload.order) != set(rows):
        raise BusinessRuleError("BAD_IMAGE_ORDER", "order must list exactly this product's image ids")
    for position, image_id in enumerate(payload.order):
        rows[image_id].sort_order = position
    session.flush()
    log_action(
        session, action="storefront.product.images_reordered", entity_type="product", entity_id=product.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"order": payload.order},
    )
    return list_product_images(product_id, ctx=ctx, session=session)


class ImagePatchIn(BaseModel):
    alt: str | None = Field(default=None, max_length=200)
    sort_order: int | None = None
    make_cover: bool | None = None


@router.patch("/products/{product_id}/images/{image_id}")
def patch_product_image(
    product_id: str, image_id: str, payload: ImagePatchIn,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db),
):
    product = _product_row(session, ctx.company_id, product_id)
    row = session.get(ProductImage, image_id)
    if row is None or row.company_id != ctx.company_id or row.product_id != product.id:
        raise NotFoundError("Product image")
    if payload.alt is not None:
        row.alt = payload.alt
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    if payload.make_cover:
        product.image_file_id = row.file_id
    session.flush()
    log_action(
        session, action="storefront.product.image_updated", entity_type="product", entity_id=product.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"image_id": row.id, "cover": bool(payload.make_cover)},
    )
    return {**_image_out(row), "is_cover": row.file_id == product.image_file_id}


@router.delete("/products/{product_id}/images/{image_id}")
def delete_product_image(
    product_id: str, image_id: str,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db),
):
    product = _product_row(session, ctx.company_id, product_id)
    row = session.get(ProductImage, image_id)
    if row is None or row.company_id != ctx.company_id or row.product_id != product.id:
        raise NotFoundError("Product image")
    file_id = row.file_id
    if product.image_file_id == file_id:
        product.image_file_id = None
    session.delete(row)
    session.flush()
    delete_file(session, file_id)
    log_action(
        session, action="storefront.product.image_deleted", entity_type="product", entity_id=product.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, before_data={"image_id": image_id, "file_id": file_id},
    )
    return {"deleted": image_id}


class CoverIn(BaseModel):
    image_id: str


@router.patch("/products/{product_id}/cover")
def set_product_cover(
    product_id: str, payload: CoverIn,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db),
):
    product = _product_row(session, ctx.company_id, product_id)
    row = session.get(ProductImage, payload.image_id)
    if row is None or row.company_id != ctx.company_id or row.product_id != product.id:
        raise NotFoundError("Product image")
    product.image_file_id = row.file_id
    session.flush()
    log_action(
        session, action="storefront.product.cover_set", entity_type="product", entity_id=product.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"image_id": row.id},
    )
    return {"product_id": product.id, "cover_file_id": row.file_id}


# ---- hero slides ----
def _hero_row(session: Session, company_id: str, slide_id: str) -> StorefrontHeroSlide:
    row = session.get(StorefrontHeroSlide, slide_id)
    if row is None or row.company_id != company_id:
        raise NotFoundError("Hero slide")
    return row


@router.get("/hero-slides")
def list_hero(ctx: CompanyCtx = Depends(guard(P_STOREFRONT_VIEW)), session: Session = Depends(get_db)):
    rows = session.execute(
        select(StorefrontHeroSlide).where(StorefrontHeroSlide.company_id == ctx.company_id)
        .order_by(StorefrontHeroSlide.sort_order, StorefrontHeroSlide.created_at)
    ).scalars().all()
    return [
        {**svc._hero_out(row), "is_active": row.is_active, "sort_order": row.sort_order}
        for row in rows
    ]


class HeroIn(BaseModel):
    eyebrow: str = Field(default="", max_length=80)
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(default="", max_length=500)
    cta: str = Field(default="Shop now", max_length=80)
    category_slug: str | None = Field(default=None, max_length=80)
    tone: str = Field(default="indigo", max_length=16)
    sort_order: int = 0
    is_active: bool = True


class HeroUpdateIn(BaseModel):
    eyebrow: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, max_length=200)
    text: str | None = Field(default=None, max_length=500)
    cta: str | None = Field(default=None, max_length=80)
    category_slug: str | None = Field(default=None, max_length=80)
    tone: str | None = Field(default=None, max_length=16)
    sort_order: int | None = None
    is_active: bool | None = None


@router.post("/hero-slides", status_code=201)
def create_hero(payload: HeroIn, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db)):
    row = StorefrontHeroSlide(company_id=ctx.company_id, created_by=ctx.user.id, **payload.model_dump())
    session.add(row)
    session.flush()
    log_action(
        session, action="storefront.hero_slide.created", entity_type="storefront_hero_slide", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"title": row.title},
    )
    return {**svc._hero_out(row), "is_active": row.is_active, "sort_order": row.sort_order}


@router.patch("/hero-slides/{slide_id}")
def update_hero(
    slide_id: str, payload: HeroUpdateIn,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db),
):
    row = _hero_row(session, ctx.company_id, slide_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    session.flush()
    log_action(
        session, action="storefront.hero_slide.updated", entity_type="storefront_hero_slide", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return {**svc._hero_out(row), "is_active": row.is_active, "sort_order": row.sort_order}


@router.post("/hero-slides/{slide_id}/image")
def upload_hero_image(
    slide_id: str, file: UploadFile,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE, P_FILES_UPLOAD)),
    session: Session = Depends(get_db),
):
    row = _hero_row(session, ctx.company_id, slide_id)
    record = save_file(
        session, file, company_id=ctx.company_id, purpose="hero_image",
        created_by=ctx.user.id, allowed_types=IMAGE_CONTENT_TYPES, visibility="public",
    )
    row.image_file_id = record.id
    session.flush()
    log_action(
        session, action="storefront.hero_slide.image_uploaded", entity_type="storefront_hero_slide", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"file_id": record.id},
    )
    return {"slide_id": row.id, "file_id": record.id, "image_url": svc.media_url(row.company_id, record.id)}


@router.delete("/hero-slides/{slide_id}")
def delete_hero(
    slide_id: str, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db),
):
    row = _hero_row(session, ctx.company_id, slide_id)
    if row.image_file_id:
        delete_file(session, row.image_file_id)
    session.delete(row)
    session.flush()
    log_action(
        session, action="storefront.hero_slide.deleted", entity_type="storefront_hero_slide", entity_id=slide_id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, before_data={"title": row.title},
    )
    return {"deleted": slide_id}


# ---- testimonials ----
class TestimonialIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    quote: str = Field(min_length=1)
    sort_order: int = 0
    is_active: bool = True


class TestimonialUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    quote: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


def _testimonial_row(session: Session, company_id: str, row_id: str) -> StorefrontTestimonial:
    row = session.get(StorefrontTestimonial, row_id)
    if row is None or row.company_id != company_id:
        raise NotFoundError("Testimonial")
    return row


@router.get("/testimonials")
def list_testimonials_admin(ctx: CompanyCtx = Depends(guard(P_STOREFRONT_VIEW)), session: Session = Depends(get_db)):
    rows = session.execute(
        select(StorefrontTestimonial).where(StorefrontTestimonial.company_id == ctx.company_id)
        .order_by(StorefrontTestimonial.sort_order, StorefrontTestimonial.created_at)
    ).scalars().all()
    return [
        {"id": r.id, "name": r.name, "city": r.city, "quote": r.quote, "sort_order": r.sort_order, "is_active": r.is_active}
        for r in rows
    ]


@router.post("/testimonials", status_code=201)
def create_testimonial(payload: TestimonialIn, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db)):
    row = StorefrontTestimonial(company_id=ctx.company_id, created_by=ctx.user.id, **payload.model_dump())
    session.add(row)
    session.flush()
    log_action(
        session, action="storefront.testimonial.created", entity_type="storefront_testimonial", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"name": row.name},
    )
    return {"id": row.id, "name": row.name, "city": row.city, "quote": row.quote, "sort_order": row.sort_order, "is_active": row.is_active}


@router.patch("/testimonials/{row_id}")
def update_testimonial(
    row_id: str, payload: TestimonialUpdateIn,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db),
):
    row = _testimonial_row(session, ctx.company_id, row_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    session.flush()
    log_action(
        session, action="storefront.testimonial.updated", entity_type="storefront_testimonial", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return {"id": row.id, "name": row.name, "city": row.city, "quote": row.quote, "sort_order": row.sort_order, "is_active": row.is_active}


@router.delete("/testimonials/{row_id}")
def delete_testimonial(row_id: str, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db)):
    row = _testimonial_row(session, ctx.company_id, row_id)
    session.delete(row)
    session.flush()
    log_action(
        session, action="storefront.testimonial.deleted", entity_type="storefront_testimonial", entity_id=row_id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return {"deleted": row_id}


# ---- FAQs ----
class FaqIn(BaseModel):
    group: str = Field(default="General", max_length=100)
    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1)
    sort_order: int = 0
    is_active: bool = True


class FaqUpdateIn(BaseModel):
    group: str | None = Field(default=None, max_length=100)
    question: str | None = Field(default=None, max_length=300)
    answer: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


def _faq_row(session: Session, company_id: str, row_id: str) -> StorefrontFaq:
    row = session.get(StorefrontFaq, row_id)
    if row is None or row.company_id != company_id:
        raise NotFoundError("FAQ")
    return row


def _faq_out(row: StorefrontFaq) -> dict:
    return {"id": row.id, "group": row.group_name, "question": row.question, "answer": row.answer, "sort_order": row.sort_order, "is_active": row.is_active}


@router.get("/faqs")
def list_faqs_admin(ctx: CompanyCtx = Depends(guard(P_STOREFRONT_VIEW)), session: Session = Depends(get_db)):
    rows = session.execute(
        select(StorefrontFaq).where(StorefrontFaq.company_id == ctx.company_id)
        .order_by(StorefrontFaq.group_name, StorefrontFaq.sort_order)
    ).scalars().all()
    return [_faq_out(row) for row in rows]


@router.post("/faqs", status_code=201)
def create_faq(payload: FaqIn, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db)):
    row = StorefrontFaq(company_id=ctx.company_id, group_name=payload.group, question=payload.question,
                        answer=payload.answer, sort_order=payload.sort_order, is_active=payload.is_active, created_by=ctx.user.id)
    session.add(row)
    session.flush()
    log_action(
        session, action="storefront.faq.created", entity_type="storefront_faq", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"question": row.question},
    )
    return _faq_out(row)


@router.patch("/faqs/{row_id}")
def update_faq(row_id: str, payload: FaqUpdateIn, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db)):
    row = _faq_row(session, ctx.company_id, row_id)
    data = payload.model_dump(exclude_unset=True)
    if "group" in data:
        row.group_name = data.pop("group")
    for field, value in data.items():
        setattr(row, field, value)
    session.flush()
    log_action(
        session, action="storefront.faq.updated", entity_type="storefront_faq", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return _faq_out(row)


@router.delete("/faqs/{row_id}")
def delete_faq(row_id: str, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db)):
    row = _faq_row(session, ctx.company_id, row_id)
    session.delete(row)
    session.flush()
    log_action(
        session, action="storefront.faq.deleted", entity_type="storefront_faq", entity_id=row_id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return {"deleted": row_id}


# ---- policies ----
class PolicyIn(BaseModel):
    slug: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    updated: str = Field(default="", max_length=40)
    sections: list[dict] = []
    sort_order: int = 0
    is_active: bool = True


class PolicyUpdateIn(BaseModel):
    slug: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=200)
    updated: str | None = Field(default=None, max_length=40)
    sections: list[dict] | None = None
    sort_order: int | None = None
    is_active: bool | None = None


def _policy_row(session: Session, company_id: str, row_id: str) -> StorefrontPolicy:
    row = session.get(StorefrontPolicy, row_id)
    if row is None or row.company_id != company_id:
        raise NotFoundError("Policy")
    return row


def _policy_admin_out(row: StorefrontPolicy) -> dict:
    return {
        "id": row.id, "slug": row.slug, "title": row.title, "updated": row.updated,
        "sections": list(row.sections or []), "sort_order": row.sort_order, "is_active": row.is_active,
    }


@router.get("/policies")
def list_policies_admin(ctx: CompanyCtx = Depends(guard(P_STOREFRONT_VIEW)), session: Session = Depends(get_db)):
    rows = session.execute(
        select(StorefrontPolicy).where(StorefrontPolicy.company_id == ctx.company_id)
        .order_by(StorefrontPolicy.sort_order, StorefrontPolicy.title)
    ).scalars().all()
    return [_policy_admin_out(row) for row in rows]


@router.post("/policies", status_code=201)
def create_policy(payload: PolicyIn, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db)):
    row = StorefrontPolicy(
        company_id=ctx.company_id, slug=payload.slug.strip().lower(), title=payload.title,
        updated=payload.updated, sections=_sections(payload.sections) or [],
        sort_order=payload.sort_order, is_active=payload.is_active, created_by=ctx.user.id,
    )
    session.add(row)
    session.flush()
    log_action(
        session, action="storefront.policy.created", entity_type="storefront_policy", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"slug": row.slug},
    )
    return _policy_admin_out(row)


@router.patch("/policies/{row_id}")
def update_policy(row_id: str, payload: PolicyUpdateIn, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db)):
    row = _policy_row(session, ctx.company_id, row_id)
    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"]:
        row.slug = data.pop("slug").strip().lower()
    if "sections" in data:
        row.sections = _sections(data.pop("sections")) or []
    for field, value in data.items():
        setattr(row, field, value)
    session.flush()
    log_action(
        session, action="storefront.policy.updated", entity_type="storefront_policy", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
    )
    return _policy_admin_out(row)


@router.delete("/policies/{row_id}")
def delete_policy(row_id: str, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db)):
    row = _policy_row(session, ctx.company_id, row_id)
    session.delete(row)
    session.flush()
    log_action(
        session, action="storefront.policy.deleted", entity_type="storefront_policy", entity_id=row_id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, before_data={"slug": row.slug},
    )
    return {"deleted": row_id}


# ---- store settings ----
class SettingsIn(BaseModel):
    free_shipping_threshold: Decimal | None = None
    flat_shipping_fee: Decimal | None = None
    contact_phone: str | None = Field(default=None, max_length=50)
    contact_email: str | None = Field(default=None, max_length=255)
    contact_address: str | None = Field(default=None, max_length=300)
    announcements: list[str] | None = None
    perks: list[dict] | None = None
    about_values: list[dict] | None = None
    about_stats: list[dict] | None = None
    footer_about: str | None = Field(default=None, max_length=300)


@router.get("/settings")
def get_settings(ctx: CompanyCtx = Depends(guard(P_STOREFRONT_VIEW)), session: Session = Depends(get_db)):
    return svc.settings_out(svc.get_settings_row(session, ctx.company_id), ctx.company_id)


@router.put("/settings")
def put_settings(payload: SettingsIn, ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE)), session: Session = Depends(get_db)):
    row = svc.get_settings_row(session, ctx.company_id)
    created = row is None
    if row is None:
        row = StorefrontSettings(company_id=ctx.company_id, created_by=ctx.user.id)
        session.add(row)
    data = payload.model_dump()
    row.free_shipping_threshold = _money(data["free_shipping_threshold"], "free_shipping_threshold")
    row.flat_shipping_fee = _money(data["flat_shipping_fee"], "flat_shipping_fee")
    row.contact_phone = data["contact_phone"]
    row.contact_email = data["contact_email"]
    row.contact_address = data["contact_address"]
    row.announcements = data["announcements"]
    row.perks = data["perks"]
    row.about_values = data["about_values"]
    row.about_stats = data["about_stats"]
    row.footer_about = data["footer_about"]
    session.flush()
    log_action(
        session, action="storefront.settings.created" if created else "storefront.settings.updated",
        entity_type="storefront_settings", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id,
        after_data={"free_shipping_threshold": str(row.free_shipping_threshold) if row.free_shipping_threshold else None},
    )
    return svc.settings_out(row, ctx.company_id)


@router.post("/settings/map-image")
def upload_map_image(
    file: UploadFile,
    ctx: CompanyCtx = Depends(guard(P_STOREFRONT_MANAGE, P_FILES_UPLOAD)),
    session: Session = Depends(get_db),
):
    row = svc.get_settings_row(session, ctx.company_id)
    if row is None:
        row = StorefrontSettings(company_id=ctx.company_id, created_by=ctx.user.id)
        session.add(row)
        session.flush()
    record = save_file(
        session, file, company_id=ctx.company_id, purpose="contact_map",
        created_by=ctx.user.id, allowed_types=IMAGE_CONTENT_TYPES, visibility="public",
    )
    row.map_image_file_id = record.id
    session.flush()
    log_action(
        session, action="storefront.settings.map_uploaded", entity_type="storefront_settings", entity_id=row.id,
        actor_user_id=ctx.user.id, company_id=ctx.company_id, after_data={"file_id": record.id},
    )
    return {"file_id": record.id, "image_url": svc.media_url(row.company_id, record.id)}
