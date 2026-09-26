/* =====================================================================
   MittiMandi Screen: Onboarding & Farmer Profile Completion
   Mandatory flow for users where user.profile_complete === false
   ===================================================================== */

import { store } from '../state.js';
import { api } from '../api.js';
import { renderBadge } from '../components/badge.js';
import { renderButton } from '../components/button.js';
import { renderCard } from '../components/card.js';
import { renderTextInput, renderSelect, renderFormGroup } from '../components/input.js';

export function renderOnboarding() {
  const user = store.get('user') || {};

  const stateOptions = [
    { value: '23', label: 'Madhya Pradesh (MP)' },
    { value: '27', label: 'Maharashtra (MH)' },
    { value: '08', label: 'Rajasthan (RJ)' },
    { value: '09', label: 'Uttar Pradesh (UP)' },
    { value: '24', label: 'Gujarat (GJ)' },
    { value: '03', label: 'Punjab (PB)' },
    { value: '06', label: 'Haryana (HR)' }
  ];

  const cropOptions = [
    { value: 'Wheat', label: 'Wheat (Sharbati / Lokwan)' },
    { value: 'Soybean', label: 'Soybean (Yellow JS-9560)' },
    { value: 'Chana', label: 'Chana (Desi JG-11)' },
    { value: 'Mustard', label: 'Mustard (Pusa Bold)' },
    { value: 'Cotton', label: 'Cotton (Medium Staple)' }
  ];

  const cardContent = `
    ${renderTextInput({
      id: 'onboard-name',
      label: 'Full Name / पूरा नाम',
      placeholder: 'e.g. Ramesh Patel',
      value: user.name !== 'Ramesh Patel' ? user.name : '',
      helper: 'As registered in Aadhaar / Land Records'
    })}

    ${renderSelect({
      id: 'onboard-state',
      label: 'State / राज्य (LGD Code)',
      options: stateOptions,
      selected: '23',
      helper: 'Primary farming jurisdiction'
    })}

    <div class="grid-2-col gap-sm">
      ${renderTextInput({
        id: 'onboard-district',
        label: 'District / जिला',
        placeholder: 'e.g. Khargone',
        value: 'Khargone'
      })}
      ${renderTextInput({
        id: 'onboard-village',
        label: 'Village / गाँव',
        placeholder: 'e.g. Kasrawad',
        value: 'Kasrawad'
      })}
    </div>

    ${renderTextInput({
      id: 'onboard-fpo',
      label: 'FPO / Cooperatives Association',
      placeholder: 'e.g. Nimar Organic Farmer Producer Co.',
      value: user.fpo || 'Nimar Kisan Producer Co.',
      helper: 'Optional: Leave empty if individual seller'
    })}

    <div class="grid-2-col gap-sm">
      ${renderTextInput({
        id: 'onboard-land',
        type: 'number',
        step: '0.1',
        min: '0.1',
        label: 'Land Holding (Acres)',
        placeholder: 'e.g. 5.5',
        value: '5.0'
      })}
      ${renderSelect({
        id: 'onboard-crop',
        label: 'Primary Crop',
        options: cropOptions,
        selected: 'Wheat'
      })}
    </div>

    <div class="auth-consent-row mt-md">
      <input type="checkbox" id="onboard-agristack-consent" checked class="form-checkbox">
      <label for="onboard-agristack-consent" class="caption text-secondary">
        I give consent to fetch my land parcel records via AgriStack / State Land Registry under DPDP Act 2023.
      </label>
    </div>
  `;

  return `
    <div class="screen-content">
      <div>
        <div class="flex-row justify-between items-center">
          ${renderBadge('ONBOARDING · PROFILE SETUP', 'primary')}
          ${renderBadge('STEP 2 OF 2', 'secondary')}
        </div>
        <h2 class="headline-md mt-xs">Complete Your Profile</h2>
        <p class="caption text-secondary">
          Required to trade on ONDC, access mandi price forecasts, and receive digital escrow settlements.
        </p>
      </div>

      ${renderCard({
        content: cardContent,
        extraClasses: 'mt-md'
      })}

      <div class="auth-action-footer">
        ${renderButton({
          text: 'Save Profile & Enter Mandi →',
          variant: 'primary',
          size: 'lg',
          isBlock: true,
          action: 'submit-onboarding'
        })}
      </div>
    </div>
  `;
}
