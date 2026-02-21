import { PrismaClient, Ticket } from '@prisma/client';

const prisma = new PrismaClient();

// Configuration for Priority Scoring
const PRIORITY_SETTINGS = {
    SLA_BREACH_PENALTY: 50,
    TIME_DECAY_RATE_PER_HOUR: 2, // 2 points per hour past creation
    REPORT_MULTIPLIER: 5,        // 5 points per duplicate report
    MAX_SCORE: 100
};

export class PriorityService {
    /**
     * Recalculates the priority score for a given ticket based on
     * ground truths: time decay, report count, social sentiment, and SLAs.
     */
    static async calculatePriority(ticketId: string): Promise<number> {
        const ticket = await prisma.ticket.findUnique({
            where: { id: ticketId }
        });

        if (!ticket) throw new Error("Ticket not found");

        let score = ticket.priorityScore; // Base score from category

        // 1. Time decay: how long has it been open?
        const hoursOpen = Math.floor((Date.now() - ticket.createdAt.getTime()) / (1000 * 60 * 60));
        score += hoursOpen * PRIORITY_SETTINGS.TIME_DECAY_RATE_PER_HOUR;

        // 2. Report Count
        score += (ticket.reportCount - 1) * PRIORITY_SETTINGS.REPORT_MULTIPLIER;

        // 3. Social Media Sentiment Boost (Mock implementation)
        score += ticket.sentimentBoost;

        // 4. SLA Breach Proximity
        if (ticket.slaDeadline) {
            const hoursToSLA = (ticket.slaDeadline.getTime() - Date.now()) / (1000 * 60 * 60);
            if (hoursToSLA <= 0) {
                score += PRIORITY_SETTINGS.SLA_BREACH_PENALTY; // Breached SLA!
            } else if (hoursToSLA <= 4) {
                score += 20; // Critical warning zone
            }
        }

        // Cap the score at MAX_SCORE dynamically mapping it to UX indicators (Critical 80+, High 60-79, Medium 35-59, Low 0-34)
        const finalScore = Math.min(score, PRIORITY_SETTINGS.MAX_SCORE);

        return finalScore;
    }

    /**
     * Reevaluates all open tickets for a particular ward (invoked via cron or API pull)
     */
    static async reevaluateWardPriorities(wardId: string): Promise<void> {
        const openTickets = await prisma.ticket.findMany({
            where: { wardId, status: { in: ['OPEN', 'ASSIGNED', 'IN_PROGRESS'] } }
        });

        for (const t of openTickets) {
            const updatedScore = await this.calculatePriority(t.id);
            if (updatedScore !== t.priorityScore) {
                await prisma.ticket.update({
                    where: { id: t.id },
                    data: { priorityScore: updatedScore }
                });
            }
        }
    }
}
