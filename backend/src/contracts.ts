import { z } from 'zod';
import {clinicalObservations} from './queue-contracts.js';
export const text = z.string().trim().min(1).max(200);
export const password = z.string().min(12).max(128);
export const email = z.string().email().max(200).transform(v=>v.toLowerCase());
export const login = z.object({email,password:z.string().min(1).max(128)}).strict();
export const profile = z.object({name:text,registrationNumber:text,location:text,phone:text,email,
  latitude:z.number().min(-90).max(90).nullable().optional(),longitude:z.number().min(-180).max(180).nullable().optional(),operatingHours:z.string().max(500).optional()}).strict();
export const registration = profile.extend({adminName:text,adminEmail:email,password});
export const catalog = z.object({departments:z.array(text).max(100),specialties:z.array(text).max(100),
  services:z.array(z.object({name:text,available:z.boolean()})).max(200),equipment:z.array(z.object({name:text,available:z.boolean()})).max(200)}).strict();
export const capacity = z.object({totalBeds:z.number().int().positive(),availableBeds:z.number().int().nonnegative(),staffOnDuty:z.number().int().nonnegative(),workload:z.enum(['Low','Medium','High']),shared:z.boolean()}).strict().refine(v=>v.availableBeds<=v.totalBeds,'Available beds exceed total beds');
export const operation = z.object({category:text,content:z.object({message:z.string().min(1).max(2000)}),visibility:z.enum(['PRIVATE','SHARED','PUBLIC']),source:text}).strict();
export const patient = z.object({identifier:text,name:text,age:z.number().int().min(0).max(130),sex:z.enum(['Female','Male','Other','Unknown'])}).strict();
export const referral = z.object({patientId:text,requiredService:text,requiredSpecialty:text.optional(),clinicalSummary:z.string().min(5).max(5000),urgency:z.enum(['Routine','Urgent','Emergency']),clinicalObservations:clinicalObservations.optional()}).strict();
export const transition = z.object({status:z.enum(['SUBMITTED','ACCEPTED','REJECTED','IN_PROGRESS','COMPLETED','CANCELLED']),destinationId:text.optional(),reason:z.string().max(2000).optional(),version:z.number().int().nonnegative()}).strict();
export const knowledge = z.object({category:text,content:z.string().min(3).max(4000),source:text,visibility:z.enum(['PRIVATE','SHARED','PUBLIC']),reviewAt:z.string().datetime().optional(),conversationId:text.optional()}).strict();
export const member = z.object({name:text,email,password,role:z.enum(['HOSPITAL_ADMIN','HEALTHCARE_WORKER']),permissions:z.array(z.enum(['REFERRAL_RECEIVE','REFERRAL_TRIAGE','KNOWLEDGE_REVIEW'])).default([])}).strict();
export const source = z.object({kind:z.enum(['WEBSITE','FACEBOOK','TELEGRAM','FEED']),url:z.string().url().max(2000).refine(v=>v.startsWith('https://'),'HTTPS required')}).strict();
