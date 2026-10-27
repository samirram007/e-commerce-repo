import { createFileRoute } from "@tanstack/react-router";
import { FeedbackPage } from "../../features/feedback/FeedbackPage";

/** Purchase feedback: review moderation and order experience (ERP). */
export const Route = createFileRoute("/_protected/feedback")({ component: FeedbackPage });
