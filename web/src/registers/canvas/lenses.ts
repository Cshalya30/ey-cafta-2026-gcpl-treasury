/**
 * The eight lenses: one graph, re-read eight ways (PRD 7.2).
 *
 * Colour never carries quantity alone. Every lens pairs a hue with a glyph or
 * a numeric badge, because people do not perceive colour values as ordered.
 */

import type { Entity } from '@/lib/types';
import type { Tone } from '@/components/primitives';

export type LensId =
  | 'cash'
  | 'forecast'
  | 'pooling'
  | 'risk'
  | 'controls'
  | 'data'
  | 'banking'
  | 'service';

export type LensReading = {
  /** The number shown on the node. Always accompanied by its unit on screen. */
  badge: string;
  /** What the badge means, for the title attribute and the screen reader. */
  badgeLabel: string;
  tone: Tone;
  /** A short word, so the state is legible without relying on the hue. */
  state: string;
  /** 0 to 1. Drives the magnitude bar, which is a second, non-colour encoding. */
  magnitude: number;
};

export type Lens = {
  id: LensId;
  key: number;
  label: string;
  nodeEncodes: string;
  edgeEncodes: string;
  read: (entity: Entity, context: LensContext) => LensReading;
};

export type LensContext = {
  maxSurplusUsd: number;
  maxExposureUsd: number;
  leakByEntity: Map<string, number>;
  breachesByEntity: Map<string, number>;
  banksByEntity: Map<string, number>;
  exposureByEntity: Map<string, { notional: number; hedged: number }>;
};

const clamp = (value: number): number => Math.max(0, Math.min(1, value));

export const LENSES: Lens[] = [
  {
    id: 'cash',
    key: 1,
    label: 'Cash',
    nodeEncodes: 'Deployable surplus magnitude',
    edgeEncodes: 'Ownership, plus the animated Cash Leak overlap',
    read: (entity, context) => {
      const surplus = entity.decomposition.deployable_surplus.usd;
      const borrowing = entity.drawn.usd;
      const isSurplus = surplus > borrowing;
      return {
        badge: isSurplus ? '+' : borrowing > 0 ? '−' : '=',
        badgeLabel: isSurplus
          ? 'Net surplus: deployable cash exceeds drawn debt'
          : borrowing > 0
            ? 'Net borrowing: drawn debt exceeds deployable cash'
            : 'Flat: neither deployable surplus nor drawn debt',
        tone: isSurplus ? 'ok' : borrowing > 0 ? 'err' : 'neutral',
        state: isSurplus ? 'surplus' : borrowing > 0 ? 'borrowing' : 'flat',
        magnitude: clamp(Math.max(surplus, borrowing) / (context.maxSurplusUsd || 1)),
      };
    },
  },
  {
    id: 'forecast',
    key: 2,
    label: '13-week forecast',
    nodeEncodes: 'Net forecast position at week four',
    edgeEncodes: 'Ownership',
    read: (entity) => {
      const submitted = entity.onboard_status === 'live';
      return {
        badge: submitted ? '✓' : '!',
        badgeLabel: submitted
          ? 'Current cycle submitted and approved'
          : 'Current cycle not approved',
        tone: submitted ? 'ok' : 'warn',
        state: submitted ? 'approved' : 'pending',
        magnitude: submitted ? 1 : 0.4,
      };
    },
  },
  {
    id: 'pooling',
    key: 3,
    label: 'Funding and pooling',
    nodeEncodes: 'Pool eligibility',
    edgeEncodes: 'Proposed and live pool flows',
    read: (entity) => {
      const tone: Tone =
        entity.pool_status === 'eligible'
          ? 'ok'
          : entity.pool_status === 'review'
            ? 'warn'
            : entity.pool_status === 'restricted'
              ? 'err'
              : 'neutral';
      return {
        badge: entity.route,
        badgeLabel: `Route ${entity.route}, pool status ${entity.pool_status.replace('_', ' ')}`,
        tone,
        state: entity.pool_status.replace('_', ' '),
        magnitude: entity.pool_status === 'eligible' ? 1 : 0.45,
      };
    },
  },
  {
    id: 'risk',
    key: 4,
    label: 'Risk and exposure',
    nodeEncodes: 'Unhedged exposure ratio',
    edgeEncodes: 'Counterparty link',
    read: (entity, context) => {
      const exposure = context.exposureByEntity.get(entity.id);
      const ratio = exposure && exposure.notional > 0 ? exposure.hedged / exposure.notional : 0;
      const unhedged = 1 - ratio;
      return {
        badge: `${Math.round(unhedged * 100)}`,
        badgeLabel: `${Math.round(unhedged * 100)} per cent of notional exposure is unhedged`,
        tone: unhedged > 0.5 ? 'err' : unhedged > 0.25 ? 'warn' : 'ok',
        state: unhedged > 0.5 ? 'unhedged' : unhedged > 0.25 ? 'partial' : 'covered',
        magnitude: clamp(unhedged),
      };
    },
  },
  {
    id: 'controls',
    key: 5,
    label: 'Controls and SoD',
    nodeEncodes: 'Open breach count',
    edgeEncodes: 'Approval path',
    read: (entity, context) => {
      const breaches = context.breachesByEntity.get(entity.id) ?? 0;
      return {
        badge: String(breaches),
        badgeLabel:
          breaches === 0
            ? 'No open segregation-of-duties breaches'
            : `${breaches} open segregation-of-duties breach(es)`,
        tone: breaches === 0 ? 'ok' : breaches > 1 ? 'err' : 'warn',
        state: breaches === 0 ? 'clear' : 'breach',
        magnitude: clamp(breaches / 3),
      };
    },
  },
  {
    id: 'data',
    key: 6,
    label: 'Data health',
    nodeEncodes: 'Feed staleness',
    edgeEncodes: 'Feed path',
    read: (entity) => {
      const bad = entity.stale_accounts + entity.offline_accounts;
      return {
        badge: `${bad}/${entity.account_count}`,
        badgeLabel: `${bad} of ${entity.account_count} account feeds are stale or offline`,
        tone: bad === 0 ? 'ok' : bad > 1 ? 'err' : 'warn',
        state: bad === 0 ? 'current' : 'degraded',
        magnitude: clamp(entity.account_count ? bad / entity.account_count : 0),
      };
    },
  },
  {
    id: 'banking',
    key: 7,
    label: 'Banking',
    nodeEncodes: 'Count of distinct banks',
    edgeEncodes: 'Account relationship',
    read: (entity, context) => {
      const banks = context.banksByEntity.get(entity.id) ?? 0;
      return {
        badge: String(banks),
        badgeLabel: `${banks} distinct bank relationship(s) across ${entity.account_count} accounts`,
        tone: banks <= 2 ? 'ok' : banks <= 4 ? 'warn' : 'err',
        state: banks <= 2 ? 'consolidated' : banks <= 4 ? 'spread' : 'fragmented',
        magnitude: clamp(banks / 6),
      };
    },
  },
  {
    id: 'service',
    key: 8,
    label: 'Service (SLA)',
    nodeEncodes: 'SLA attainment',
    edgeEncodes: 'Reporting line',
    read: (entity) => {
      // Attainment is derived from the share of this entity's feeds that are
      // current: a hub cannot answer within SLA on a balance it does not have.
      const attainment = entity.coverage_pct;
      return {
        badge: `${Math.round(attainment * 100)}`,
        badgeLabel: `${Math.round(attainment * 100)} per cent SLA attainment, from feed currency`,
        tone: attainment >= 0.95 ? 'ok' : attainment >= 0.8 ? 'warn' : 'err',
        state: attainment >= 0.95 ? 'on target' : 'below target',
        magnitude: clamp(attainment),
      };
    },
  },
];

export const lensById = (id: string): Lens => LENSES.find((lens) => lens.id === id) ?? LENSES[0]!;
