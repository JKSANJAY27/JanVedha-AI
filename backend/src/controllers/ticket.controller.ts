import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { PriorityService } from '../services/priority.service';
import { AuthRequest } from '../middleware/auth.middleware';

const prisma = new PrismaClient();

export class TicketController {

    // POST /api/tickets - Create a new ticket (Citizen or Agent)
    static async createTicket(req: AuthRequest, res: Response) {
        try {
            const { title, description, category, latitude, longitude, wardId, departmentId } = req.body;
            const createdById = req.user?.id; // Assuming user is injected by auth middleware

            if (!createdById) return res.status(401).json({ error: "Unauthorized" });

            // Auto-generate ticket number
            const count = await prisma.ticket.count();
            const ticketNumber = `CIV-${new Date().getFullYear()}-${(count + 1).toString().padStart(5, '0')}`;

            // Default SLA based on category (simplified mock logic)
            const slaDeadline = new Date();
            slaDeadline.setHours(slaDeadline.getHours() + 48); // 48 hours for general

            const ticket = await prisma.ticket.create({
                data: {
                    ticketNumber,
                    title,
                    description,
                    category,
                    latitude,
                    longitude,
                    wardId,
                    departmentId,
                    createdById,
                    slaDeadline
                }
            });

            // Calculate initial priority score
            const score = await PriorityService.calculatePriority(ticket.id);

            const updatedTicket = await prisma.ticket.update({
                where: { id: ticket.id },
                data: { priorityScore: score }
            });

            res.status(201).json(updatedTicket);
        } catch (error: any) {
            res.status(500).json({ error: error.message });
        }
    }

    // GET /api/tickets/ward/:wardId
    static async getTicketsForWard(req: AuthRequest, res: Response) {
        try {
            const wardId = req.params.wardId as string;

            const tickets = await prisma.ticket.findMany({
                where: { wardId },
                orderBy: { priorityScore: 'desc' }, // Order by priority automatically!
                include: {
                    assignedOfficer: { select: { name: true, phone: true } },
                    department: { select: { name: true } }
                }
            });

            res.json(tickets);
        } catch (error: any) {
            res.status(500).json({ error: error.message });
        }
    }

    // PATCH /api/tickets/:id/status (Ward Officer closing or assigning)
    static async updateStatus(req: AuthRequest, res: Response) {
        try {
            const id = req.params.id as string;
            const { status, assignedOfficerId } = req.body;

            const updateData: any = { status };
            if (assignedOfficerId) updateData.assignedOfficerId = assignedOfficerId;
            if (status === 'RESOLVED') updateData.resolvedAt = new Date();
            if (status === 'CLOSED') updateData.closedAt = new Date();

            const ticket = await prisma.ticket.update({
                where: { id },
                data: updateData
            });

            // Log the action
            await prisma.auditLog.create({
                data: {
                    action: `STATUS_UPDATED_TO_${status}`,
                    ticketId: ticket.id,
                    userId: req.user!.id,
                    details: `Assigned API user updated the status.`
                }
            });

            res.json(ticket);
        } catch (error: any) {
            res.status(500).json({ error: error.message });
        }
    }

    // GET /api/tickets/city (Commissioner Dashboard)
    static async getCitywideDashboard(req: AuthRequest, res: Response) {
        try {
            // Aggregate ticket statuses
            const statusCounts = await prisma.ticket.groupBy({
                by: ['status'],
                _count: { id: true }
            });

            // Top 10 Critical tickets for immediate attention
            const criticalTickets = await prisma.ticket.findMany({
                orderBy: { priorityScore: 'desc' },
                take: 10,
                include: { ward: true, department: true }
            });

            // Ward-wise performance mock-up (In production, group by wardId and calculate breached SLAs)
            const wards = await prisma.ward.findMany({
                include: {
                    _count: {
                        select: { tickets: true }
                    }
                }
            });

            const wardPerformance = wards.map((w: any) => ({
                wardId: w.id,
                wardName: w.name,
                totalTickets: w._count.tickets,
                slaCompliance: Math.floor(Math.random() * 20 + 80), // Mock 80-100% compliance
                sentimentScore: Math.floor(Math.random() * 40 + 60) // Mock 60-100 score
            })).sort((a: any, b: any) => b.slaCompliance - a.slaCompliance);

            res.json({
                statusCounts,
                criticalTickets,
                wardPerformance
            });
        } catch (error: any) {
            res.status(500).json({ error: error.message });
        }
    }
}
