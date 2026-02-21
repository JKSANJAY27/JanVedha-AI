import { Request, Response } from 'express';
import { PrismaClient } from '@prisma/client';
import jwt from 'jsonwebtoken';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();
const JWT_SECRET = process.env.JWT_SECRET || 'fallback_secret_key_hackathon_only';

export class AuthController {

    // POST /api/auth/login
    static async login(req: Request, res: Response) {
        try {
            const { email, password } = req.body;

            const user = await prisma.user.findUnique({ where: { email } });
            if (!user) {
                return res.status(401).json({ error: 'Invalid credentials' });
            }

            // Mocking password check during hackathon if hashes aren't fully seeded
            const isMatch = user.passwordHash ? await bcrypt.compare(password, user.passwordHash) : password === 'password123';
            if (!isMatch) {
                return res.status(401).json({ error: 'Invalid credentials' });
            }

            // Generate JWT with full role hierarchy profile
            const payload = {
                id: user.id,
                role: user.role,
                wardId: user.wardId,
                zoneId: user.zoneId,
                departmentId: user.departmentId
            };

            const token = jwt.sign(payload, JWT_SECRET, { expiresIn: '1d' });

            res.json({ token, user: payload });
        } catch (error: any) {
            res.status(500).json({ error: error.message });
        }
    }

    // POST /api/auth/register (For citizen registration)
    static async registerCitizen(req: Request, res: Response) {
        try {
            const { name, email, phone, password } = req.body;

            const passwordHash = await bcrypt.hash(password, 10);

            const newUser = await prisma.user.create({
                data: {
                    name,
                    email,
                    phone,
                    passwordHash,
                    role: 'CITIZEN'
                }
            });

            res.status(201).json({ message: 'User created', userId: newUser.id });
        } catch (error: any) {
            res.status(500).json({ error: error.message });
        }
    }
}
