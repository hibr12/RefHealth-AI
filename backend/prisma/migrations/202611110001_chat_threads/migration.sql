BEGIN;

CREATE TABLE "ChatThread" (
  "id" TEXT NOT NULL,
  "hospital_id" TEXT NOT NULL,
  "userId" TEXT NOT NULL,
  "title" TEXT NOT NULL DEFAULT 'New chat',
  "version" INTEGER NOT NULL DEFAULT 0,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "ChatThread_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "ChatThread_hospital_id_fkey" FOREIGN KEY ("hospital_id") REFERENCES "Hospital"("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
CREATE UNIQUE INDEX "ChatThread_id_hospital_id_userId_key" ON "ChatThread"("id","hospital_id","userId");
CREATE INDEX "ChatThread_hospital_id_userId_updatedAt_id_idx" ON "ChatThread"("hospital_id","userId","updatedAt","id");

ALTER TABLE "Conversation" ADD COLUMN "threadId" TEXT,
  ADD COLUMN "sequence" INTEGER,
  ADD COLUMN "clientRequestId" TEXT,
  ADD COLUMN "requestDigest" TEXT,
  ADD COLUMN "attachmentKind" TEXT;

-- Older turns have no session boundary. Preserve every original row and collect
-- each owner's existing history into one explicitly labelled legacy thread.
INSERT INTO "ChatThread" ("id","hospital_id","userId","title","version","createdAt","updatedAt")
SELECT MIN("id"),"hospital_id","userId",'Earlier conversations',COUNT(*)::integer,MIN("createdAt"),MAX("createdAt")
FROM "Conversation" GROUP BY "hospital_id","userId";

WITH ordered AS (
  SELECT c."id",t."id" AS thread_id,
    ROW_NUMBER() OVER (PARTITION BY c."hospital_id",c."userId" ORDER BY c."createdAt",c."id")::integer AS sequence
  FROM "Conversation" c JOIN "ChatThread" t ON t."hospital_id"=c."hospital_id" AND t."userId"=c."userId"
)
UPDATE "Conversation" c SET "threadId"=ordered.thread_id,"sequence"=ordered.sequence FROM ordered WHERE c."id"=ordered."id";

ALTER TABLE "Conversation" ALTER COLUMN "threadId" SET NOT NULL,ALTER COLUMN "sequence" SET NOT NULL;
CREATE UNIQUE INDEX "Conversation_clientRequestId_key" ON "Conversation"("clientRequestId");
CREATE UNIQUE INDEX "Conversation_threadId_sequence_key" ON "Conversation"("threadId","sequence");
ALTER TABLE "Conversation" ADD CONSTRAINT "Conversation_threadId_hospital_id_userId_fkey"
  FOREIGN KEY ("threadId","hospital_id","userId") REFERENCES "ChatThread"("id","hospital_id","userId") ON DELETE RESTRICT ON UPDATE CASCADE;

COMMIT;
