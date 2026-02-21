import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
    console.log('Seeding Janvedha AI Database...');

    // 1. Create Core Hierarchy
    const zoneCenter = await prisma.zone.create({
        data: { name: 'Zone Center (Mock)' }
    });

    const wardA = await prisma.ward.create({
        data: { name: 'Ward 42 - Downtown', zoneId: zoneCenter.id }
    });

    const deptRoads = await prisma.department.create({
        data: { name: 'Roads & Highways' }
    });

    const deptElec = await prisma.department.create({
        data: { name: 'Electrical' }
    });

    // 2. Create Default Users (Password: hackathon2026)
    const defaultPassword = await bcrypt.hash('hackathon2026', 10);

    const commissioner = await prisma.user.create({
        data: {
            name: 'Dr. Anita Desai (Commissioner)',
            email: 'commissioner@janvedha.gov.in',
            passwordHash: defaultPassword,
            role: 'COMMISSIONER'
        }
    });

    const wardOfficer = await prisma.user.create({
        data: {
            name: 'Ramesh Kumar (Ward Officer - 42)',
            email: 'ward42@janvedha.gov.in',
            passwordHash: defaultPassword,
            role: 'WARD_OFFICER',
            wardId: wardA.id
        }
    });

    const citizen = await prisma.user.create({
        data: {
            name: 'Priya Sharma (Citizen)',
            email: 'priya@example.com',
            passwordHash: defaultPassword,
            role: 'CITIZEN'
        }
    });

    // 3. Create initial tickets for the dashboard
    await prisma.ticket.create({
        data: {
            ticketNumber: 'CIV-2026-00001',
            title: 'Massive Pothole on Main Rd',
            description: 'Multiple cars damaged. Needs immediate attention.',
            category: 'Road Hazard',
            priorityScore: 92,
            reportCount: 15,
            wardId: wardA.id,
            departmentId: deptRoads.id,
            createdById: citizen.id,
            assignedOfficerId: wardOfficer.id,
            status: 'OPEN'
        }
    });

    console.log('Seed completed successfully.');
}

main()
    .catch((e) => {
        console.error(e);
        process.exit(1);
    })
    .finally(async () => {
        await prisma.$disconnect();
    });
