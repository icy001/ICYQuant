{{/* vim: set filetype=mustache: */}}
{{/* Expand the name of the chart. */}}
{{- define "icyquant.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Create a default fully qualified app name. */}}
{{- define "icyquant.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/* Create chart name and version as used by the chart label. */}}
{{- define "icyquant.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Common labels */}}
{{- define "icyquant.labels" -}}
helm.sh/chart: {{ include "icyquant.chart" }}
{{ include "icyquant.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/* Selector labels */}}
{{- define "icyquant.selectorLabels" -}}
app.kubernetes.io/name: {{ include "icyquant.name" }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* Service labels */}}
{{- define "icyquant.serviceLabels" -}}
{{ include "icyquant.labels" . }}
app.kubernetes.io/component: {{ .Values.serviceType | default "service" }}
{{- end }}

{{/* Generate the name of the service */}}
{{- define "icyquant.serviceName" -}}
{{- printf "%s-%s" .Release.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}
