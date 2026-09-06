export const VERIFICATION_TYPES = {
  identity: {
    key: 'identity',
    labelKey: 'identityCheck',
    listHref: '/dashboard/verification/identity',
    count: 21,
    columns: ['user', 'documentType', 'submittedAt', 'priority', 'status'],
  },

  property: {
    key: 'property',
    labelKey: 'propertyCheck',
    listHref: '/dashboard/verification/property',
    count: 18,
    columns: ['requestOwner', 'propertyType', 'area', 'city', 'submittedAt', 'status'],
  },

  lawyers: {
    key: 'lawyers',
    labelKey: 'lawyerApproval',
    listHref: '/dashboard/verification/lawyers',
    count: 8,
    columns: ['lawyer', 'licenseNumber', 'submittedAt', 'specialty', 'status'],
  },
}

export const VERIFICATION_ORDER = [
  'identity',
  'property',
  'lawyers',
]

export function getVerificationConfig(type) {
  return (
    VERIFICATION_TYPES[type] ??
    VERIFICATION_TYPES.identity
  )
}

export function getVerificationColumns(type) {
  return getVerificationConfig(type).columns
}

export function getTotalVerificationCount() {
  return VERIFICATION_ORDER.reduce(
    (total, type) => total + VERIFICATION_TYPES[type].count,
    0,
  )
}
