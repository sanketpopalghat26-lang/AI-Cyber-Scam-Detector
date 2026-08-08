# =============================================================================
# Helm Helpers — AI Cyber Scam Detector
# =============================================================================
{{- define "scam-detector.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "scam-detector.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "scam-detector.labels" -}}
helm.sh/chart: {{ include "scam-detector.name" . }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "scam-detector.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: scam-detector
{{- end }}

{{- define "scam-detector.selectorLabels" -}}
app.kubernetes.io/name: {{ include "scam-detector.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "scam-detector.backend.labels" -}}
{{ include "scam-detector.labels" . }}
app.kubernetes.io/component: backend
app.kubernetes.io/tier: api
{{- end }}

{{- define "scam-detector.frontend.labels" -}}
{{ include "scam-detector.labels" . }}
app.kubernetes.io/component: frontend
app.kubernetes.io/tier: web
{{- end }}

{{- define "scam-detector.backend.selectorLabels" -}}
{{ include "scam-detector.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{- define "scam-detector.frontend.selectorLabels" -}}
{{ include "scam-detector.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{- define "scam-detector.imagePullSecrets" -}}
{{- if .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- range .Values.global.imagePullSecrets }}
  - name: {{ . }}
{{- end }}
{{- end }}
{{- end }}

{{- define "scam-detector.probes" -}}
{{- $probes := .probes }}
{{- $port := .port }}
livenessProbe:
  httpGet:
    path: {{ $probes.liveness.path }}
    port: {{ $port }}
  initialDelaySeconds: {{ $probes.liveness.initialDelaySeconds }}
  periodSeconds: {{ $probes.liveness.periodSeconds }}
  timeoutSeconds: {{ $probes.liveness.timeoutSeconds }}
  failureThreshold: {{ $probes.liveness.failureThreshold }}
readinessProbe:
  httpGet:
    path: {{ $probes.readiness.path }}
    port: {{ $port }}
  initialDelaySeconds: {{ $probes.readiness.initialDelaySeconds }}
  periodSeconds: {{ $probes.readiness.periodSeconds }}
  timeoutSeconds: {{ $probes.readiness.timeoutSeconds }}
  failureThreshold: {{ $probes.readiness.failureThreshold }}
startupProbe:
  httpGet:
    path: {{ $probes.startup.path }}
    port: {{ $port }}
  initialDelaySeconds: {{ $probes.startup.initialDelaySeconds }}
  periodSeconds: {{ $probes.startup.periodSeconds }}
  timeoutSeconds: {{ $probes.startup.timeoutSeconds }}
  failureThreshold: {{ $probes.startup.failureThreshold }}
{{- end }}
