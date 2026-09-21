class AppError(Exception):
    """Domain or request failure rendered as a JSON:API error document."""

    def __init__(self, status_code: int, title: str, detail: str | None = None) -> None:
        super().__init__(detail or title)
        self.status_code = status_code
        self.title = title
        self.detail = detail


def error_document(
    status_code: int,
    title: str,
    detail: str | None = None,
    pointer: str | None = None,
) -> dict:
    error: dict = {"status": str(status_code), "title": title}
    if detail:
        error["detail"] = detail
    if pointer:
        error["source"] = {"pointer": pointer}
    return {"errors": [error]}
