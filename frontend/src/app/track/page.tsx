"use client";

// This page is the plain /track route without a code in the URL
// Renders the same TrackTicketPage but without pre-filling a ticket code
import TrackTicketPage from "./[code]/page";

export default function TrackPage() {
    return <TrackTicketPage />;
}
