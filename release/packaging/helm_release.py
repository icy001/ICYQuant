"""
Helm packaging for ICYQuant Kubernetes deployments.

Generates Helm chart configurations including Chart.yaml, values.yaml,
and templates for deployment, service, ingress, configmap, secrets,
HPA (HorizontalPodAutoscaler), and PDB (PodDisruptionBudget).
Supports multi-environment values (dev, staging, prod), ServiceMonitor
for Prometheus, and PodDisruptionBudget.
"""

from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class HelmEnvironment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


@dataclass
class HelmChartConfig:
    chart_name: str
    chart_version: str
    app_version: str
    description: str
    service_name: str
    service_port: int
    target_port: int
    replica_count: int = 2
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "256Mi"
    memory_limit: str = "512Mi"
    enable_ingress: bool = False
    ingress_host: str = ""
    enable_hpa: bool = False
    hpa_min_replicas: int = 2
    hpa_max_replicas: int = 10
    hpa_cpu_target: int = 70
    enable_pdb: bool = True
    pdb_min_available: int = 1
    enable_service_monitor: bool = False
    service_monitor_interval: str = "30s"
    env_vars: dict[str, str] = field(default_factory=dict)
    configmap_data: dict[str, str] = field(default_factory=dict)
    secret_keys: list[str] = field(default_factory=list)
    annotations: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class GeneratedTemplate:
    path: str
    content: str
    template_type: str


@dataclass
class HelmReleaseResult:
    success: bool
    chart_path: str = ""
    generated_templates: list[GeneratedTemplate] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    environment: HelmEnvironment = HelmEnvironment.DEV
    chart_valid: bool = False
    files_valid: bool = False

    @property
    def template_paths(self) -> list[str]:
        return [t.path for t in self.generated_templates]


class HelmRelease:
    """
    Generates Helm chart configurations for ICYQuant services.

    Creates complete Helm charts with all necessary templates for
    Kubernetes deployment, including autoscaling, ingress, monitoring,
    and disruption budget management.
    """

    def __init__(self, output_dir: str = "deploy/helm") -> None:
        self.output_dir = output_dir
        self._charts: list[HelmChartConfig] = []

    def add_chart(self, config: HelmChartConfig) -> None:
        self._charts.append(config)

    def generate(
        self, environment: HelmEnvironment
    ) -> HelmReleaseResult:
        templates: list[GeneratedTemplate] = []
        errors: list[str] = []
        warnings: list[str] = []

        for config in self._charts:
            chart_dir = os.path.join(
                self.output_dir, config.chart_name
            )
            templates_dir = os.path.join(chart_dir, "templates")

            try:
                chart_yaml = self._generate_chart_yaml(config)
                templates.append(GeneratedTemplate(
                    path=os.path.join(chart_dir, "Chart.yaml"),
                    content=chart_yaml,
                    template_type="chart",
                ))

                values_yaml = self._generate_values_yaml(config, environment)
                templates.append(GeneratedTemplate(
                    path=os.path.join(chart_dir, "values.yaml"),
                    content=values_yaml,
                    template_type="values",
                ))

                if environment != HelmEnvironment.DEV:
                    env_values = self._generate_env_values(config, environment)
                    templates.append(GeneratedTemplate(
                        path=os.path.join(
                            chart_dir, f"values-{environment.value}.yaml"
                        ),
                        content=env_values,
                        template_type="env-values",
                    ))

                templates.extend(self._generate_templates(config, templates_dir))

            except Exception as e:
                errors.append(
                    f"Failed to generate chart {config.chart_name}: {e}"
                )

        success = len(errors) == 0
        chart_valid = self._validate_chart_structure(templates)
        return HelmReleaseResult(
            success=success,
            chart_path=os.path.join(
                self.output_dir, self._charts[0].chart_name
            ) if self._charts else "",
            generated_templates=templates,
            validation_errors=errors,
            warnings=warnings,
            environment=environment,
            chart_valid=chart_valid,
            files_valid=chart_valid and not errors,
        )

    def _generate_chart_yaml(self, config: HelmChartConfig) -> str:
        return textwrap.dedent(f"""\
            apiVersion: v2
            name: {config.chart_name}
            description: {config.description}
            type: application
            version: {config.chart_version}
            appVersion: "{config.app_version}"
            keywords:
              - icyquant
              - quantitative
              - trading
            maintainers:
              - name: ICYQuant Team
                email: dev@icyquant.io
            annotations:
              category: Trading Platform
        """)

    def _generate_values_yaml(
        self, config: HelmChartConfig, environment: HelmEnvironment
    ) -> str:
        labels_str = self._dict_to_yaml_labels(config.labels)
        annotations_str = self._dict_to_yaml_labels(config.annotations)

        ingress_block = ""
        if config.enable_ingress:
            ingress_block = textwrap.dedent(f"""\

              ingress:
                enabled: {"true" if config.enable_ingress else "false"}
                className: nginx
                annotations:
                  kubernetes.io/ingress.class: nginx
                hosts:
                  - host: {config.ingress_host}
                    paths:
                      - path: /
                        pathType: Prefix
                        port: {config.target_port}
                tls:
                  - secretName: {config.service_name}-tls
                    hosts:
                      - {config.ingress_host}
            """)

        hpa_block = ""
        if config.enable_hpa:
            hpa_block = textwrap.dedent(f"""\

              autoscaling:
                enabled: {"true" if config.enable_hpa else "false"}
                minReplicas: {config.hpa_min_replicas}
                maxReplicas: {config.hpa_max_replicas}
                targetCPUUtilizationPercentage: {config.hpa_cpu_target}
            """)

        return textwrap.dedent(f"""\
            # Default values for {config.chart_name}
            # Environment: {environment.value}

            replicas: {config.replica_count}

            image:
              repository: icyquant/{config.service_name}
              tag: "{config.app_version}"
              pullPolicy: IfNotPresent

            service:
              type: ClusterIP
              port: {config.service_port}
              targetPort: {config.target_port}
              annotations:
            {textwrap.indent(annotations_str, "    ")}

            resources:
              requests:
                cpu: {config.cpu_request}
                memory: {config.memory_request}
              limits:
                cpu: {config.cpu_limit}
                memory: {config.memory_limit}
            {hpa_block}
            {ingress_block}

            podDisruptionBudget:
              enabled: {"true" if config.enable_pdb else "false"}
              minAvailable: {config.pdb_min_available}

            serviceMonitor:
              enabled: {"true" if config.enable_service_monitor else "false"}
              interval: {config.service_monitor_interval}
              namespace: monitoring

            configmap:
              data:
            {self._dict_to_yaml_multiline(config.configmap_data, "    ")}

            secrets:
              keys:
            {self._list_to_yaml(config.secret_keys, "    ")}

            env:
            {self._dict_to_yaml_multiline(config.env_vars, "    ")}

            nodeSelector: {{}}
            tolerations: []
            affinity: {{}}

            labels:
            {textwrap.indent(labels_str, "  ")}
        """)

    def _generate_env_values(
        self, config: HelmChartConfig, environment: HelmEnvironment
    ) -> str:
        env_overrides: dict[str, object] = {}
        if environment == HelmEnvironment.STAGING:
            env_overrides = {
                "replicas": max(1, config.replica_count - 1),
                "resources": {
                    "requests": {"cpu": "100m", "memory": "256Mi"},
                    "limits": {"cpu": "500m", "memory": "512Mi"},
                },
            }
        elif environment == HelmEnvironment.PROD:
            env_overrides = {
                "replicas": config.replica_count,
                "resources": {
                    "requests": {"cpu": config.cpu_request, "memory": config.memory_request},
                    "limits": {"cpu": config.cpu_limit, "memory": config.memory_limit},
                },
            }

        overrides_str = self._dict_to_yaml_multiline(env_overrides, "")
        return textwrap.dedent(f"""\
            # {environment.value} environment overrides for {config.chart_name}
            # Auto-generated - do not edit manually

            {overrides_str}
        """)

    def _generate_templates(
        self, config: HelmChartConfig, templates_dir: str
    ) -> list[GeneratedTemplate]:
        templates: list[GeneratedTemplate] = []

        templates.append(GeneratedTemplate(
            path=os.path.join(templates_dir, "_helpers.tpl"),
            content=self._generate_helpers(config),
            template_type="helper",
        ))

        templates.append(GeneratedTemplate(
            path=os.path.join(templates_dir, "deployment.yaml"),
            content=self._generate_deployment(config),
            template_type="deployment",
        ))

        templates.append(GeneratedTemplate(
            path=os.path.join(templates_dir, "service.yaml"),
            content=self._generate_service(config),
            template_type="service",
        ))

        if config.enable_ingress:
            templates.append(GeneratedTemplate(
                path=os.path.join(templates_dir, "ingress.yaml"),
                content=self._generate_ingress(config),
                template_type="ingress",
            ))

        templates.append(GeneratedTemplate(
            path=os.path.join(templates_dir, "configmap.yaml"),
            content=self._generate_configmap(config),
            template_type="configmap",
        ))

        templates.append(GeneratedTemplate(
            path=os.path.join(templates_dir, "secrets.yaml"),
            content=self._generate_secrets(config),
            template_type="secrets",
        ))

        if config.enable_hpa:
            templates.append(GeneratedTemplate(
                path=os.path.join(templates_dir, "hpa.yaml"),
                content=self._generate_hpa(config),
                template_type="hpa",
            ))

        if config.enable_pdb:
            templates.append(GeneratedTemplate(
                path=os.path.join(templates_dir, "pdb.yaml"),
                content=self._generate_pdb(config),
                template_type="pdb",
            ))

        if config.enable_service_monitor:
            templates.append(GeneratedTemplate(
                path=os.path.join(templates_dir, "servicemonitor.yaml"),
                content=self._generate_service_monitor(config),
                template_type="servicemonitor",
            ))

        return templates

    def _generate_helpers(self, config: HelmChartConfig) -> str:
        return textwrap.dedent(f"""\
            {{/*
            Expand the name of the chart.
            */}}
            {{- define "{config.chart_name}.name" -}}
            {{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
            {{- end }}

            {{/*
            Create a default fully qualified app name.
            */}}
            {{- define "{config.chart_name}.fullname" -}}
            {{- $name := default .Chart.Name .Values.nameOverride }}
            {{- if contains $name .Release.Name }}
            {{- .Release.Name | trunc 63 | trimSuffix "-" }}
            {{- else }}
            {{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
            {{- end }}
            {{- end }}

            {{/*
            Create chart name and version as used by the chart label.
            */}}
            {{- define "{config.chart_name}.chart" -}}
            {{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
            {{- end }}

            {{/*
            Common labels
            */}}
            {{- define "{config.chart_name}.labels" -}}
            helm.sh/chart: {{ include "{config.chart_name}.chart" . }}
            app.kubernetes.io/name: {{ include "{config.chart_name}.name" . }}
            app.kubernetes.io/instance: {{ .Release.Name }}
            app.kubernetes.io/version: {{ .Chart.AppVersion }}
            app.kubernetes.io/managed-by: {{ .Release.Service }}
            {{- end }}

            {{/*
            Selector labels
            */}}
            {{- define "{config.chart_name}.selectorLabels" -}}
            app.kubernetes.io/name: {{ include "{config.chart_name}.name" . }}
            app.kubernetes.io/instance: {{ .Release.Name }}
            {{- end }}
        """)

    def _generate_deployment(self, config: HelmChartConfig) -> str:
        return textwrap.dedent(f"""\
            apiVersion: apps/v1
            kind: Deployment
            metadata:
              name: {{{{ include "{config.chart_name}.fullname" . }}}}
              labels:
                {{{{ include "{config.chart_name}.labels" . }}}}
                app.kubernetes.io/component: {config.service_name}
            spec:
              replicas: {{{{ .Values.replicas }}}}
              selector:
                matchLabels:
                  {{{{ include "{config.chart_name}.selectorLabels" . }}}}
              template:
                metadata:
                  labels:
                    {{{{ include "{config.chart_name}.selectorLabels" . }}}}
                    app.kubernetes.io/component: {config.service_name}
                  annotations:
                    prometheus.io/scrape: "true"
                    prometheus.io/port: "{config.service_port}"
                spec:
                  containers:
                    - name: {config.service_name}
                      image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag }}}}"
                      imagePullPolicy: {{{{ .Values.image.pullPolicy }}}}
                      ports:
                        - name: http
                          containerPort: {config.target_port}
                          protocol: TCP
                      env:
                        - name: APP_ENV
                          value: "{{{{ .Release.Namespace }}}}"
                        - name: SERVICE_NAME
                          value: "{config.service_name}"
                      envFrom:
                        - configMapRef:
                            name: {{{{ include "{config.chart_name}.fullname" . }}}}-config
                            optional: true
                        - secretRef:
                            name: {{{{ include "{config.chart_name}.fullname" . }}}}-secrets
                            optional: true
                      resources:
                        requests:
                          cpu: {{{{ .Values.resources.requests.cpu }}}}
                          memory: {{{{ .Values.resources.requests.memory }}}}
                        limits:
                          cpu: {{{{ .Values.resources.limits.cpu }}}}
                          memory: {{{{ .Values.resources.limits.memory }}}}
                      livenessProbe:
                        httpGet:
                          path: /health
                          port: http
                        initialDelaySeconds: 10
                        periodSeconds: 30
                        timeoutSeconds: 5
                        failureThreshold: 3
                      readinessProbe:
                        httpGet:
                          path: /health
                          port: http
                        initialDelaySeconds: 5
                        periodSeconds: 10
                        timeoutSeconds: 3
                        failureThreshold: 3
                      startupProbe:
                        httpGet:
                          path: /health
                          port: http
                        initialDelaySeconds: 0
                        periodSeconds: 5
                        timeoutSeconds: 3
                        failureThreshold: 30
                  serviceAccountName: {config.service_name}-sa
                  securityContext:
                    runAsNonRoot: true
                    runAsUser: 1000
                    fsGroup: 1000
                  {{- with .Values.nodeSelector }}
                  nodeSelector:
                    {{{{ toYaml . | nindent 6 }}}}
                  {{- end }}
                  {{- with .Values.tolerations }}
                  tolerations:
                    {{{{ toYaml . | nindent 6 }}}}
                  {{- end }}
                  {{- with .Values.affinity }}
                  affinity:
                    {{{{ toYaml . | nindent 6 }}}}
                  {{- end }}
        """)

    def _generate_service(self, config: HelmChartConfig) -> str:
        return textwrap.dedent(f"""\
            apiVersion: v1
            kind: Service
            metadata:
              name: {{{{ include "{config.chart_name}.fullname" . }}}}
              labels:
                {{{{ include "{config.chart_name}.labels" . }}}}
              annotations:
                {{{{ toYaml .Values.service.annotations | nindent 4 }}}}
            spec:
              type: {{{{ .Values.service.type }}}}
              ports:
                - name: http
                  port: {config.service_port}
                  targetPort: {config.target_port}
                  protocol: TCP
              selector:
                {{{{ include "{config.chart_name}.selectorLabels" . }}}}
        """)

    def _generate_ingress(self, config: HelmChartConfig) -> str:
        return textwrap.dedent(f"""\
            {{{{- if .Values.ingress.enabled -}}}}
            apiVersion: networking.k8s.io/v1
            kind: Ingress
            metadata:
              name: {{{{ include "{config.chart_name}.fullname" . }}}}
              labels:
                {{{{ include "{config.chart_name}.labels" . }}}}
              annotations:
                {{{{ toYaml .Values.ingress.annotations | nindent 4 }}}}
            spec:
              ingressClassName: {{{{ .Values.ingress.className }}}}
              tls:
                {{{{- range .Values.ingress.tls }}}}
                - hosts:
                    {{{{- range .hosts }}}}
                    - {{{{ . }}}}
                    {{{{- end }}}}
                  secretName: {{{{ .secretName }}}}
                {{{{- end }}}}
              rules:
                {{{{- range .Values.ingress.hosts }}}}
                - host: {{{{ .host }}}}
                  http:
                    paths:
                      {{{{- range .paths }}}}
                      - path: {{{{ .path }}}}
                        pathType: {{{{ .pathType }}}}
                        backend:
                          service:
                            name: {{{{ include "{config.chart_name}.fullname" $ }}}}
                            port:
                              number: {{{{ .port }}}}
                      {{{{- end }}}}
                {{{{- end }}}}
            {{{{- end }}}}
        """)

    def _generate_configmap(self, config: HelmChartConfig) -> str:
        return textwrap.dedent(f"""\
            apiVersion: v1
            kind: ConfigMap
            metadata:
              name: {{{{ include "{config.chart_name}.fullname" . }}}}-config
              labels:
                {{{{ include "{config.chart_name}.labels" . }}}}
            data:
              {{{{ toYaml .Values.configmap.data | nindent 2 }}}}
        """)

    def _generate_secrets(self, config: HelmChartConfig) -> str:
        return textwrap.dedent(f"""\
            apiVersion: v1
            kind: Secret
            metadata:
              name: {{{{ include "{config.chart_name}.fullname" . }}}}-secrets
              labels:
                {{{{ include "{config.chart_name}.labels" . }}}}
            type: Opaque
            data:
              {{{{ toYaml .Values.secrets | nindent 2 }}}}
        """)

    def _generate_hpa(self, config: HelmChartConfig) -> str:
        return textwrap.dedent(f"""\
            {{{{- if .Values.autoscaling.enabled -}}}}
            apiVersion: autoscaling/v2
            kind: HorizontalPodAutoscaler
            metadata:
              name: {{{{ include "{config.chart_name}.fullname" . }}}}
              labels:
                {{{{ include "{config.chart_name}.labels" . }}}}
            spec:
              scaleTargetRef:
                apiVersion: apps/v1
                kind: Deployment
                name: {{{{ include "{config.chart_name}.fullname" . }}}}
              minReplicas: {{{{ .Values.autoscaling.minReplicas }}}}
              maxReplicas: {{{{ .Values.autoscaling.maxReplicas }}}}
              metrics:
                - type: Resource
                  resource:
                    name: cpu
                    target:
                      type: Utilization
                      averageUtilization: {{{{ .Values.autoscaling.targetCPUUtilizationPercentage }}}}
              behavior:
                scaleDown:
                  stabilizationWindowSeconds: 300
                  policies:
                    - type: Percent
                      value: 50
                      periodSeconds: 60
                scaleUp:
                  stabilizationWindowSeconds: 60
                  policies:
                    - type: Percent
                      value: 100
                      periodSeconds: 30
                    - type: Pods
                      value: 2
                      periodSeconds: 30
                  selectPolicy: Max
            {{{{- end }}}}
        """)

    def _generate_pdb(self, config: HelmChartConfig) -> str:
        return textwrap.dedent(f"""\
            {{{{- if .Values.podDisruptionBudget.enabled -}}}}
            apiVersion: policy/v1
            kind: PodDisruptionBudget
            metadata:
              name: {{{{ include "{config.chart_name}.fullname" . }}}}
              labels:
                {{{{ include "{config.chart_name}.labels" . }}}}
            spec:
              minAvailable: {{{{ .Values.podDisruptionBudget.minAvailable }}}}
              selector:
                matchLabels:
                  {{{{ include "{config.chart_name}.selectorLabels" . }}}}
            {{{{- end }}}}
        """)

    def _generate_service_monitor(self, config: HelmChartConfig) -> str:
        return textwrap.dedent(f"""\
            {{{{- if .Values.serviceMonitor.enabled -}}}}
            apiVersion: monitoring.coreos.com/v1
            kind: ServiceMonitor
            metadata:
              name: {{{{ include "{config.chart_name}.fullname" . }}}}
              labels:
                {{{{ include "{config.chart_name}.labels" . }}}}
                release: prometheus
            spec:
              selector:
                matchLabels:
                  {{{{ include "{config.chart_name}.selectorLabels" . }}}}
              endpoints:
                - port: http
                  interval: {{{{ .Values.serviceMonitor.interval }}}}
                  scheme: http
                  path: /metrics
              namespaceSelector:
                matchNames:
                  - {{{{ .Release.Namespace }}}}
            {{{{- end }}}}
        """)

    def _validate_chart_structure(
        self, templates: list[GeneratedTemplate]
    ) -> bool:
        required_files = {"Chart.yaml", "values.yaml"}
        template_files = {
            os.path.basename(t.path) for t in templates
        }
        return required_files.issubset(template_files)

    @staticmethod
    def _dict_to_yaml_labels(
        data: dict[str, str], indent: str = ""
    ) -> str:
        if not data:
            return f"{indent}{{}}}}"
        lines = [f"{indent}{{}}}}"]
        for key, value in data.items():
            lines.append(f"{indent}{key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _dict_to_yaml_multiline(
        data: dict, indent: str = ""
    ) -> str:
        if not data:
            return f"{indent}{{}}}}"
        result = []
        for key, value in data.items():
            if isinstance(value, dict):
                result.append(f"{indent}{key}:")
                for k, v in value.items():
                    result.append(f"{indent}  {k}: {v}")
            else:
                result.append(f"{indent}{key}: {value}")
        return "\n".join(result)

    @staticmethod
    def _list_to_yaml(
        data: list[str], indent: str = ""
    ) -> str:
        if not data:
            return f"{indent}- placeholder"
        result = []
        for item in data:
            result.append(f"{indent}- {item}")
        return "\n".join(result)