import express, { Request, Response } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import ticketRoutes from './routes/ticket.routes';
import authRoutes from './routes/auth.routes';

dotenv.config();

const app = express();
const port = process.env.PORT || 4000;

app.use(cors());
app.use(express.json());

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/tickets', ticketRoutes);

// Basic health check endpoint
app.get('/api/health', (req: Request, res: Response) => {
    res.json({ status: 'ok', message: 'Janvedha AI API is running' });
});

app.listen(port, () => {
    console.log(`Server is running on port ${port}`);
});
