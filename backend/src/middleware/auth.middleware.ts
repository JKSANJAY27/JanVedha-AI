import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'fallback_secret_key_hackathon_only';

// Map specific roles to integers for permission level checking
const roleHierarchy: Record<string, number> = {
    'CITIZEN': 1,
    'WARD_COUNCILLOR': 2,
    'WARD_OFFICER': 3,
    'ZONAL_OFFICER': 4,
    'DEPARTMENT_HEAD': 5,
    'COMMISSIONER': 6,
    'SUPER_ADMIN': 7
};

export interface AuthRequest extends Request<any, any, any, any> {
    user?: {
        id: string;
        role: string;
        wardId?: string | null;
        zoneId?: string | null;
        departmentId?: string | null;
    };
}

export const authenticate = (req: AuthRequest, res: Response, next: NextFunction) => {
    const token = req.headers.authorization?.split(' ')[1];

    if (!token) {
        return res.status(401).json({ error: 'Unauthorized: No token provided' });
    }

    try {
        const decoded = jwt.verify(token, JWT_SECRET) as any;
        req.user = decoded;
        next();
    } catch (error) {
        return res.status(403).json({ error: 'Forbidden: Invalid token' });
    }
};

/**
 * Ensures the user has at least the minimum role level required.
 */
export const requireRoleLevel = (minRoleName: string) => {
    return (req: AuthRequest, res: Response, next: NextFunction) => {
        if (!req.user) return res.status(401).json({ error: 'Unauthorized' });

        const userLevel = roleHierarchy[req.user.role] || 0;
        const requiredLevel = roleHierarchy[minRoleName] || 99;

        if (userLevel < requiredLevel) {
            return res.status(403).json({ error: `Forbidden: Requires ${minRoleName} or higher.` });
        }

        next();
    };
};

/**
 * Middleware ensuring Ward Officers only access data within their assigned ward.
 */
export const restrictToWard = (req: AuthRequest, res: Response, next: NextFunction) => {
    if (!req.user) return res.status(401).json({ error: 'Unauthorized' });

    // Commissioners and Super Admins bypass ward restriction
    if (['COMMISSIONER', 'SUPER_ADMIN'].includes(req.user.role)) {
        return next();
    }

    // WARD_OFFICER and WARD_COUNCILLOR must be restricted to their ward
    if (['WARD_OFFICER', 'WARD_COUNCILLOR'].includes(req.user.role)) {
        const targetWardId = req.params.wardId || req.query.wardId || req.body.wardId;
        if (targetWardId && req.user.wardId !== targetWardId) {
            return res.status(403).json({ error: 'Forbidden: Cannot access data outside your assigned ward.' });
        }
    }

    next();
};
