BEGIN;
-- CreateEnum
CREATE TYPE "ClinicalPriority" AS ENUM ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW');

-- AlterTable
ALTER TABLE "Referral" ADD COLUMN     "acknowledgedAt" TIMESTAMPTZ(3),
ADD COLUMN     "acknowledgedBy" TEXT,
ADD COLUMN     "acknowledgementDueAt" TIMESTAMPTZ(3),
ADD COLUMN     "acknowledgementWarningAt" TIMESTAMPTZ(3),
ADD COLUMN     "aiPriority" "ClinicalPriority",
ADD COLUMN     "assessedAt" TIMESTAMPTZ(3),
ADD COLUMN     "assessmentStatus" TEXT NOT NULL DEFAULT 'PENDING',
ADD COLUMN     "clinicalObservations" JSONB NOT NULL DEFAULT '{}',
ADD COLUMN     "confirmedAt" TIMESTAMPTZ(3),
ADD COLUMN     "confirmedBy" TEXT,
ADD COLUMN     "confirmedPriority" "ClinicalPriority",
ADD COLUMN     "overdueNotifiedAt" TIMESTAMPTZ(3),
ADD COLUMN     "priorityExplanation" TEXT NOT NULL DEFAULT 'Clinical review required; no approved protocol has been applied.',
ADD COLUMN     "priorityRank" INTEGER NOT NULL DEFAULT 4,
ADD COLUMN     "queuePolicySnapshot" JSONB NOT NULL DEFAULT '{}',
ADD COLUMN     "receivedAt" TIMESTAMPTZ(3),
ADD COLUMN     "submittedAt" TIMESTAMPTZ(3),
ADD COLUMN     "warningNotifiedAt" TIMESTAMPTZ(3);

-- CreateTable
CREATE TABLE "QueuePolicy" (
    "hospital_id" TEXT NOT NULL,
    "timezone" TEXT NOT NULL DEFAULT 'Africa/Nairobi',
    "deadlines" JSONB NOT NULL DEFAULT '{}',
    "emergencyProcedure" TEXT NOT NULL DEFAULT '',
    "protocol" JSONB,
    "version" INTEGER NOT NULL DEFAULT 0,
    "updatedBy" TEXT NOT NULL,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "QueuePolicy_pkey" PRIMARY KEY ("hospital_id")
);

-- CreateTable
CREATE TABLE "ReferralQueueEvent" (
    "id" TEXT NOT NULL,
    "referralId" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "actorId" TEXT,
    "previousPriority" "ClinicalPriority",
    "priority" "ClinicalPriority",
    "reason" TEXT NOT NULL,
    "details" JSONB NOT NULL DEFAULT '{}',
    "createdAt" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ReferralQueueEvent_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ReferralQueueEvent_referralId_createdAt_id_idx" ON "ReferralQueueEvent"("referralId", "createdAt", "id");

-- CreateIndex
CREATE INDEX "Referral_destinationId_priorityRank_receivedAt_id_idx" ON "Referral"("destinationId", "priorityRank", "receivedAt", "id");

-- CreateIndex
CREATE INDEX "Referral_assessmentStatus_status_idx" ON "Referral"("assessmentStatus", "status");

-- CreateIndex
CREATE INDEX "Referral_acknowledgedAt_acknowledgementDueAt_idx" ON "Referral"("acknowledgedAt", "acknowledgementDueAt");

-- AddForeignKey
ALTER TABLE "QueuePolicy" ADD CONSTRAINT "QueuePolicy_hospital_id_fkey" FOREIGN KEY ("hospital_id") REFERENCES "Hospital"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ReferralQueueEvent" ADD CONSTRAINT "ReferralQueueEvent_referralId_fkey" FOREIGN KEY ("referralId") REFERENCES "Referral"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- Only historical events with evidence are backfilled. Receipt time is deliberately unknown.
UPDATE "Referral" r SET "submittedAt" = (SELECT MIN(h."createdAt") AT TIME ZONE 'UTC' FROM "ReferralHistory" h WHERE h."referralId"=r.id AND h.status='SUBMITTED'),
"acknowledgedAt" = (SELECT MIN(h."createdAt") AT TIME ZONE 'UTC' FROM "ReferralHistory" h WHERE h."referralId"=r.id AND h.status IN ('ACCEPTED','REJECTED')),
"acknowledgedBy" = (SELECT h."actorId" FROM "ReferralHistory" h WHERE h."referralId"=r.id AND h.status IN ('ACCEPTED','REJECTED') ORDER BY h."createdAt",h.id LIMIT 1),
"assessmentStatus" = CASE WHEN r.status='DRAFT' THEN 'PENDING' ELSE 'REVIEW_REQUIRED' END;
CREATE FUNCTION protect_referral_handoff_times() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD."receivedAt" IS NOT NULL AND NEW."receivedAt" IS DISTINCT FROM OLD."receivedAt" THEN RAISE EXCEPTION 'Receipt time is immutable'; END IF;
 IF OLD."submittedAt" IS NOT NULL AND NEW."submittedAt" IS DISTINCT FROM OLD."submittedAt" THEN RAISE EXCEPTION 'Submission time is immutable'; END IF;
 IF OLD."acknowledgedAt" IS NOT NULL AND (NEW."acknowledgedAt" IS DISTINCT FROM OLD."acknowledgedAt" OR NEW."acknowledgedBy" IS DISTINCT FROM OLD."acknowledgedBy") THEN RAISE EXCEPTION 'Acknowledgement is immutable'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_referral_handoff_times BEFORE UPDATE ON "Referral" FOR EACH ROW EXECUTE FUNCTION protect_referral_handoff_times();

COMMIT;
