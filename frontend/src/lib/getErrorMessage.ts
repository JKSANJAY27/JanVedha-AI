/**
 * Safely extracts a human-readable string from an Axios error response.
 *
 * FastAPI returns `detail` in several forms:
 *   - string  → plain HTTPException message  e.g. "Not found"
 *   - object[] → Pydantic 422 validation errors each with { type, loc, msg, input }
 *   - object  → custom dict e.g. { message: "...", question: "..." } from TicketService
 *
 * Passing an array or object directly to toast.error() causes React to crash
 * because it tries to render a non-string value as a child.
 */
export function getErrorMessage(err: any, fallback = "Something went wrong."): string {
    const detail = err?.response?.data?.detail;

    if (Array.isArray(detail)) {
        // Pydantic validation error list → join the human messages
        return detail.map((e: any) => e?.msg ?? String(e)).join("; ") || fallback;
    }

    if (typeof detail === "string" && detail.trim()) {
        return detail;
    }

    if (detail && typeof detail === "object") {
        // e.g. { message: "Please clarify your complaint", question: "..." }
        const parts: string[] = [];
        if (detail.message) parts.push(detail.message);
        if (detail.question) parts.push(detail.question);
        if (parts.length) return parts.join(" — ");
        return JSON.stringify(detail);
    }

    if (typeof err?.message === "string" && err.message.trim()) {
        return err.message;
    }

    return fallback;
}
