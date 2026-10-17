"""Import every module's models so Base.metadata is complete for Alembic."""
from app.db.base import Base  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.companies import models as companies_models  # noqa: F401
from app.modules.fiscal_years import models as fiscal_models  # noqa: F401
from app.modules.periods import models as periods_models  # noqa: F401
from app.modules.accounting import models as accounting_models  # noqa: F401
from app.modules.taxes import models as taxes_models  # noqa: F401
from app.modules.catalog import models as catalog_models  # noqa: F401
from app.modules.partners import models as partners_models  # noqa: F401
from app.modules.storage import models as storage_models  # noqa: F401
from app.modules.inventory import models as inventory_models  # noqa: F401
from app.modules.purchasing import models as purchasing_models  # noqa: F401
from app.modules.payments import models as payments_models  # noqa: F401
from app.modules.payroll import models as payroll_models  # noqa: F401
from app.modules.sales import models as sales_models  # noqa: F401
from app.modules.invoicing import models as invoicing_models  # noqa: F401
from app.modules.fulfillment import models as fulfillment_models  # noqa: F401
from app.modules.returns import models as returns_models  # noqa: F401
from app.shared.numbering import DocumentSequence  # noqa: F401
from app.shared.idempotency import IdempotencyRecord  # noqa: F401
from app.shared.files import StoredFile  # noqa: F401

metadata = Base.metadata
