-- CreateTable
CREATE TABLE "SourceJob" (
    "id" TEXT NOT NULL,
    "sourceId" TEXT NOT NULL,
    "hospital_id" TEXT NOT NULL,
    "actorId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "error" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SourceJob_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "SourceJob_status_createdAt_idx" ON "SourceJob"("status", "createdAt");

-- CreateIndex
CREATE INDEX "SourceJob_hospital_id_idx" ON "SourceJob"("hospital_id");

-- AddForeignKey
ALTER TABLE "SourceJob" ADD CONSTRAINT "SourceJob_sourceId_fkey" FOREIGN KEY ("sourceId") REFERENCES "ExternalSource"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
