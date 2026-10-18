/**
 * UI state only: persona, display currency, theme preference.
 *
 * Everything else is either server state (TanStack Query) or URL state (nuqs).
 * Keeping this store small is deliberate: a filter that lives here instead of
 * in the URL is a view a treasury user cannot paste to an approver.
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { DisplayCurrency } from './format';

export type ConsentState = 'unknown' | 'granted' | 'declined';

type UiState = {
  persona: string;
  display: DisplayCurrency;
  consent: ConsentState;
  setPersona: (persona: string) => void;
  setDisplay: (display: DisplayCurrency) => void;
  setConsent: (consent: ConsentState) => void;
};

/**
 * A storage shim that refuses to write until the viewer has accepted.
 *
 * Browser storage can be absent or throw in a private window, with blocked
 * site data, or during a thumbnail capture, so every access is guarded and the
 * app renders correctly when it comes back empty.
 */
const guardedStorage = {
  getItem: (name: string): string | null => {
    try {
      return window.localStorage.getItem(name);
    } catch {
      return null;
    }
  },
  setItem: (name: string, value: string): void => {
    try {
      const parsed = JSON.parse(value) as { state?: { consent?: ConsentState } };
      if (parsed.state?.consent !== 'granted') return;
      window.localStorage.setItem(name, value);
    } catch {
      /* storage unavailable: preferences simply do not persist */
    }
  },
  removeItem: (name: string): void => {
    try {
      window.localStorage.removeItem(name);
    } catch {
      /* nothing to do */
    }
  },
};

export const useUi = create<UiState>()(
  persist(
    (set) => ({
      persona: 'P2',
      display: 'USD',
      consent: 'unknown',
      setPersona: (persona) => set({ persona }),
      setDisplay: (display) => set({ display }),
      setConsent: (consent) => {
        if (consent === 'declined') guardedStorage.removeItem('gcpl-ui');
        set({ consent });
      },
    }),
    {
      name: 'gcpl-ui',
      storage: createJSONStorage(() => guardedStorage),
      partialize: (state) => ({
        persona: state.persona,
        display: state.display,
        consent: state.consent,
      }),
    },
  ),
);

/**
 * USD to INR for the INR display toggle.
 *
 * Held as a single constant that the state bootstrap overwrites from the API's
 * own rate, so the browser never invents an FX rate of its own.
 */
let usdToInr = 83.0;
export const setUsdToInr = (rate: number): void => {
  if (Number.isFinite(rate) && rate > 0) usdToInr = rate;
};
export const getUsdToInr = (): number => usdToInr;
