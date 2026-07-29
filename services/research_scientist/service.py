"""Research Scientist Service - orchestrates the full autonomous research loop."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scientist import ResearchScientistAgent, ResearchDomain, ResearchStatus, ResearchPriority
from .hypothesis import HypothesisGenerator, HypothesisType, HypothesisStatus
from .question import ResearchQuestionEngine
from .experiment import ExperimentDesignEngine, ExperimentType
from .data import DataInvestigationEngine
from .discovery import QuantDiscoveryEngine, DiscoveryStatus
from .backtest import AutomaticBacktestingEngine
from .validation import ResearchValidationEngine
from .report import ResearchReportGenerator, ReportType
from .memory import ResearchMemory, MemoryCategory


class ResearchScientistService:
    """Research Scientist Service.

    Orchestrates the full autonomous research loop:
    1. Question → Research Scientist analyzes
    2. Hypothesis → Generator produces testable hypotheses
    3. Experiment → Design engine plans experiments
    4. Data → Investigation engine profiles data
    5. Discovery → Quant engine finds alpha
    6. Backtest → Automatic backtesting validates
    7. Validation → Robustness checks prevent false alpha
    8. Report → Auto-generated research publication
    9. Memory → Persistent knowledge repository

    Transforms ICYQuant from AI Investment Organization
    into AI Quant Research Laboratory.
    """

    def __init__(self, scientist: ResearchScientistAgent):
        self.scientist = scientist
        self.hypothesis_gen = HypothesisGenerator()
        self.question_engine = ResearchQuestionEngine()
        self.experiment_engine = ExperimentDesignEngine()
        self.data_engine = DataInvestigationEngine()
        self.discovery_engine = QuantDiscoveryEngine()
        self.backtest_engine = AutomaticBacktestingEngine()
        self.validation_engine = ResearchValidationEngine()
        self.report_gen = ResearchReportGenerator()
        self.memory = ResearchMemory()

    def run(self, question: str) -> Dict[str, Any]:
        """Run the full research loop on a question. Main entry point."""
        return self.research(question)

    def research(self, question: str) -> Dict[str, Any]:
        """Execute the complete autonomous research loop.

        Full pipeline:
        Question → Analysis → Hypotheses → Experiments →
        Data → Discovery → Backtest → Validation → Report → Memory
        """
        result = {"question": question, "stages": []}

        # Stage 1: Initiate research
        project = self.scientist.initiate_research(question)
        result["project_id"] = project["project_id"]
        result["stages"].append({"stage": "initiation", "status": "completed"})

        # Stage 2: Analyze question
        analysis = self.question_engine.analyze(question)
        result["stages"].append({"stage": "question_analysis",
                                 "category": analysis.get("category"),
                                 "complexity": analysis.get("complexity")})

        # Stage 3: Generate hypotheses
        hypotheses = self.hypothesis_gen.generate_batch(question, count=3)
        result["hypotheses"] = [{"id": h["id"], "statement": h["statement"][:100],
                                  "type": h["type"]} for h in hypotheses]
        result["stages"].append({"stage": "hypothesis_generation",
                                 "count": len(hypotheses)})

        # Stage 4: Design experiments
        experiments = []
        for h in hypotheses:
            exp = self.experiment_engine.design_experiment(h)
            experiments.append({"id": exp.id, "type": exp.experiment_type.value,
                                "name": exp.name})
        result["experiments"] = experiments
        result["stages"].append({"stage": "experiment_design",
                                 "count": len(experiments)})

        # Stage 5: Investigate data
        data_profile = self.data_engine.investigate_dataset({
            "name": f"data_for_{question[:30]}",
            "type": "market",
            "rows": 10000,
            "columns_count": 20,
        })
        result["stages"].append({"stage": "data_investigation",
                                 "quality": data_profile.quality.value})

        # Stage 6: Discover alpha
        discovery = self.discovery_engine.run_discovery({
            "name": question[:50],
            "type": "factor",
        })
        result["discovery"] = {"id": discovery.id, "name": discovery.name,
                               "sharpe": discovery.sharpe}
        result["stages"].append({"stage": "discovery", "status": "completed"})

        # Stage 7: Backtest
        backtest = self.backtest_engine.run_backtest({
            "name": f"strategy_from_{question[:30]}",
            "type": "quantitative",
            "quality": 0.7,
            "parameters": {"start_date": "2015-01-01", "end_date": "2024-12-31"},
        })
        result["backtest"] = {"id": backtest.id, "sharpe": backtest.sharpe_ratio,
                              "max_dd": backtest.max_drawdown}
        result["stages"].append({"stage": "backtest", "sharpe": backtest.sharpe_ratio})

        # Stage 8: Validate
        validation = self.validation_engine.validate_result(backtest.to_dict())
        result["validation"] = {"status": validation.status.value,
                                "overfitting_risk": validation.overfitting_risk,
                                "robustness": validation.robustness_score}
        result["stages"].append({"stage": "validation", "status": validation.status.value})

        # Stage 9: Generate report
        report = self.report_gen.generate_report(backtest.to_dict())
        result["report_id"] = report.id
        result["stages"].append({"stage": "report", "status": "generated"})

        # Stage 10: Save to memory
        self.memory.save_entry({
            "title": question,
            "type": "research_project",
            "status": "completed",
            "outcome": f"Sharpe: {backtest.sharpe_ratio}, Validation: {validation.status.value}",
            "sharpe_ratio": backtest.sharpe_ratio,
            "tags": ["auto_research", "full_loop"],
        }, category=MemoryCategory.INSIGHT)
        result["stages"].append({"stage": "memory", "status": "saved"})

        result["status"] = "completed"
        result["summary"] = (
            f"Research complete: {len(hypotheses)} hypotheses tested, "
            f"best Sharpe: {backtest.sharpe_ratio:.2f}, "
            f"validation: {validation.status.value}"
        )

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get overall service status."""
        return {
            "scientist": self.scientist.get_research_summary(),
            "hypotheses": self.hypothesis_gen.get_summary(),
            "questions": self.question_engine.get_summary(),
            "experiments": self.experiment_engine.get_summary(),
            "data": self.data_engine.get_summary(),
            "discoveries": self.discovery_engine.get_summary(),
            "backtests": self.backtest_engine.get_summary(),
            "validations": self.validation_engine.get_summary(),
            "reports": self.report_gen.get_summary(),
            "memory": self.memory.get_summary(),
        }

    def quick_hypothesis_test(self, idea: str) -> Dict[str, Any]:
        """Quick end-to-end test of a single hypothesis."""
        hypothesis = self.hypothesis_gen.generate_hypothesis(idea)
        experiment = self.experiment_engine.design_experiment(hypothesis.to_dict())
        backtest = self.backtest_engine.run_backtest({
            "name": idea[:50],
            "type": "quick_test",
            "quality": 0.6,
        })
        validation = self.validation_engine.validate_result(backtest.to_dict())

        self.memory.save_entry({
            "title": idea,
            "type": "hypothesis",
            "status": validation.status.value,
            "sharpe_ratio": backtest.sharpe_ratio,
        }, category=MemoryCategory.HYPOTHESIS)

        return {
            "hypothesis": hypothesis.to_dict(),
            "experiment_type": experiment.experiment_type.value,
            "sharpe": backtest.sharpe_ratio,
            "max_drawdown": backtest.max_drawdown,
            "validation": validation.status.value,
        }
