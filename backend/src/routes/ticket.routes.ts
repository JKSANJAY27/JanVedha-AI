import { Router } from 'express';
import { TicketController } from '../controllers/ticket.controller';
import { authenticate, requireRoleLevel, restrictToWard } from '../middleware/auth.middleware';

const router = Router();

// Protect all routes
router.use(authenticate);

// CITIZEN and above can create tickets
router.post('/', requireRoleLevel('CITIZEN'), TicketController.createTicket);

// WARD_OFFICER, ZONAL_OFFICER, and above can view ward tickets
// restrictToWard ensures officers can only view their own ward
router.get('/ward/:wardId', requireRoleLevel('WARD_OFFICER'), restrictToWard, TicketController.getTicketsForWard);

// WARD_OFFICER assigns technicians or closes tickets
router.patch('/:id/status', requireRoleLevel('WARD_OFFICER'), TicketController.updateStatus);

// COMMISSIONER ONLY route for city-wide dashboard aggregation
router.get('/city/dashboard', requireRoleLevel('COMMISSIONER'), TicketController.getCitywideDashboard);

export default router;
