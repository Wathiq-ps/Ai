import { Badge } from '@/components/ui/Badge'
import { formatDateTime } from '@/config/locales'

function getPriority(requests, requestId) {
  const orderedRequests = [...requests].sort(
    (a, b) => new Date(a.submittedAt) - new Date(b.submittedAt),
  )

  const index = orderedRequests.findIndex(
    (request) => request.id === requestId,
  )

  if (index === 0) return 'high'
  if (index === 1) return 'medium'
  return 'low'
}

function getVerificationLabel(t, group, value) {
  return t.verificationCenter[group]?.[value] ?? value
}

function getStatusLabel(request, { t }) {
  return getVerificationLabel(t, 'statuses', request.status)
}

function getDocumentTypeLabel(request, { t }) {
  return getVerificationLabel(
    t,
    'documentTypes',
    request.documentType,
  )
}

function getPropertyTypeLabel(request, { t }) {
  return getVerificationLabel(
    t,
    'propertyTypes',
    request.propertyType,
  )
}

function getSpecialtyLabel(request, { t }) {
  return getVerificationLabel(
    t,
    'specialties',
    request.specialty,
  )
}

function getPriorityLabel(priority, { t }) {
  return getVerificationLabel(t, 'priorities', priority)
}

function formatSubmittedAt(request, { locale }) {
  return formatDateTime(request.submittedAt, locale)
}

function getPriorityVariant(priority) {
  if (priority === 'high') return 'danger'
  if (priority === 'medium') return 'warning'
  return 'muted'
}

export const CELL_RENDERERS = {
  identity: {
    user: (request) => request.name,

    documentType: getDocumentTypeLabel,

    submittedAt: formatSubmittedAt,

    priority: (request, { requests, t }) => {
      const priority = getPriority(requests, request.id)

      return (
        <Badge variant={getPriorityVariant(priority)}>
          {getPriorityLabel(priority, { t })}
        </Badge>
      )
    },

    status: getStatusLabel,
  },

  property: {
    requestOwner: (request) => (
      <div>
        <div className="font-semibold text-brand-navy">
          {request.id}
        </div>

        <div className="mt-0.5 text-[11px] text-ink-faint">
          {request.name}
        </div>
      </div>
    ),

    propertyType: getPropertyTypeLabel,

    area: (request) => request.area,

    city: (request) => request.city,

    submittedAt: formatSubmittedAt,

    status: getStatusLabel,
  },

  lawyers: {
    lawyer: (request) => request.name,

    licenseNumber: (request) => request.licenseNumber,

    submittedAt: formatSubmittedAt,

    specialty: getSpecialtyLabel,

    status: getStatusLabel,
  },
}

export function renderVerificationCell(
  type,
  key,
  request,
  context,
) {
  const renderer = CELL_RENDERERS[type]?.[key]

  if (!renderer) {
    return null
  }

  return renderer(request, context)
}