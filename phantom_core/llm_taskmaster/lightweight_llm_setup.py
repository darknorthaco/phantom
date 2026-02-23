"""
Lightweight LLM Task Master for GTX 1080
Optimized for intelligent task routing with minimal resource usage
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

# Import socket client for communication
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "phantom_core"))

try:
    from socket_integration import LLMTaskMasterClient
except ImportError:
    # Fallback implementation
    LLMTaskMasterClient = None

logger = logging.getLogger(__name__)


class LightweightLLMTaskMaster:
    """Lightweight LLM Task Master optimized for GTX 1080"""

    def __init__(self, controller_host: str = "localhost", socket_port: int = 8081):
        self.controller_host = controller_host
        self.socket_port = socket_port
        self.socket_client = None
        self.running = False

        # LLM configuration for GTX 1080 (8GB VRAM)
        self.model_config = {
            "model_size": "small",  # Lightweight model
            "max_memory_mb": 2048,  # 2GB max usage
            "context_length": 1024,  # Reasonable context
            "batch_size": 1,  # Single request processing
            "precision": "fp16",  # Half precision for efficiency
        }

        # Task routing knowledge base
        self.gpu_profiles = {
            "RTX 5080": {
                "performance_tier": "flagship",
                "memory_gb": 24,
                "tensor_cores": "4th_gen",
                "best_for": ["large_model_inference", "training", "real_time_ai"],
                "score_multiplier": 10.0,
            },
            "RTX 5060": {
                "performance_tier": "mainstream",
                "memory_gb": 16,
                "tensor_cores": "4th_gen",
                "best_for": ["ml_inference", "image_processing", "medium_training"],
                "score_multiplier": 7.0,
            },
            "GTX 1080": {
                "performance_tier": "legacy",
                "memory_gb": 8,
                "tensor_cores": "none",
                "best_for": [
                    "stable_inference",
                    "compatibility_testing",
                    "llm_task_master",
                ],
                "score_multiplier": 5.0,
            },
            "FirePro W9100": {
                "performance_tier": "professional",
                "memory_gb": 16,
                "tensor_cores": "none",
                "best_for": [
                    "data_processing",
                    "large_dataset_analysis",
                    "memory_intensive_tasks",
                ],
                "score_multiplier": 6.0,
            },
        }

        # Task type preferences
        self.task_preferences = {
            "ml_inference": {
                "preferred_features": ["tensor_cores", "high_memory"],
                "avoid_features": [],
                "memory_requirement": "medium",
            },
            "training": {
                "preferred_features": ["tensor_cores", "high_memory"],
                "avoid_features": [],
                "memory_requirement": "high",
            },
            "large_model_inference": {
                "preferred_features": ["tensor_cores", "high_memory"],
                "avoid_features": [],
                "memory_requirement": "very_high",
            },
            "data_processing": {
                "preferred_features": ["high_memory"],
                "avoid_features": [],
                "memory_requirement": "high",
            },
            "image_processing": {
                "preferred_features": ["tensor_cores"],
                "avoid_features": [],
                "memory_requirement": "low",
            },
            "stable_inference": {
                "preferred_features": ["proven_stability"],
                "avoid_features": [],
                "memory_requirement": "low",
            },
        }

        # Decision history for learning
        self.decision_history = []
        self.max_history = 100

        # Performance tracking
        self.metrics = {
            "decisions_made": 0,
            "average_decision_time": 0.0,
            "accuracy_feedback": [],
            "start_time": datetime.now(),
        }

    async def initialize(self):
        """Initialize the LLM Task Master"""
        try:
            logger.info("🤖 Initializing Lightweight LLM Task Master")

            # Initialize socket connection if available
            if LLMTaskMasterClient:
                self.socket_client = LLMTaskMasterClient(
                    self.controller_host, self.socket_port
                )

                connected = await self.socket_client.connect_as_llm_taskmaster()
                if connected:
                    logger.info("🔌 Connected to socket infrastructure")
                    # Start listening for routing requests
                    asyncio.create_task(self.listen_for_requests())
                else:
                    logger.warning("🔌 Failed to connect to socket infrastructure")
                    self.socket_client = None

            # Load or initialize the lightweight model
            await self.load_lightweight_model()

            self.running = True
            logger.info("✅ LLM Task Master initialized successfully")

        except Exception as e:
            logger.error(f"LLM Task Master initialization failed: {e}")
            raise

    async def load_lightweight_model(self):
        """Load or simulate lightweight routing model"""
        try:
            # In a real implementation, this would load a small language model
            # For now, we'll simulate with intelligent rule-based routing

            logger.info("🧠 Loading lightweight routing model...")

            # Simulate model loading time
            await asyncio.sleep(2.0)

            # Initialize routing intelligence
            self.routing_intelligence = {
                "model_loaded": True,
                "model_type": "rule_based_with_learning",
                "memory_usage_mb": 512,  # Simulated memory usage
                "inference_time_ms": 50,  # Fast inference
            }

            logger.info("✅ Lightweight routing model loaded")

        except Exception as e:
            logger.error(f"Failed to load routing model: {e}")
            raise

    async def listen_for_requests(self):
        """Listen for routing requests from the socket infrastructure"""
        if not self.socket_client:
            return

        async def message_handler(message: Dict[str, Any]):
            try:
                if message.get("type") == "routing_request":
                    await self.handle_routing_request(message)
                elif message.get("type") == "system_state":
                    await self.handle_system_state_update(message)

            except Exception as e:
                logger.error(f"Error handling message: {e}")

        try:
            await self.socket_client.listen(message_handler)
        except Exception as e:
            logger.error(f"Error in message listener: {e}")

    async def handle_routing_request(self, message: Dict[str, Any]):
        """Handle routing request from controller"""
        try:
            request_id = message.get("request_id")
            routing_data = message.get("data", {})

            # Extract task and worker information
            task = routing_data.get("task", {})
            available_workers = routing_data.get("available_workers", {})

            # Make routing decision
            decision_start = datetime.now()
            selected_worker = await self.make_routing_decision(task, available_workers)
            decision_time = (datetime.now() - decision_start).total_seconds()

            # Generate reasoning
            reasoning = await self.generate_reasoning(
                task, available_workers, selected_worker
            )

            # Send response
            response = {
                "type": "llm_routing_response",
                "request_id": request_id,
                "selected_worker": selected_worker,
                "confidence": await self.calculate_confidence(
                    task, available_workers, selected_worker
                ),
                "reasoning": reasoning,
                "decision_time_ms": decision_time * 1000,
                "timestamp": datetime.now().isoformat(),
            }

            await self.socket_client.send(response)

            # Update metrics
            self.metrics["decisions_made"] += 1
            self.update_average_decision_time(decision_time)

            # Store decision for learning
            self.store_decision(task, available_workers, selected_worker, reasoning)

            logger.info(
                f"🎯 Routing decision made: {selected_worker} (confidence: {response['confidence']:.2f})"
            )

        except Exception as e:
            logger.error(f"Error handling routing request: {e}")

    async def make_routing_decision(
        self, task: Dict[str, Any], available_workers: Dict[str, Any]
    ) -> Optional[str]:
        """Make intelligent routing decision using lightweight AI"""

        if not available_workers:
            return None

        task_type = task.get("task_type", "unknown")
        task_params = task.get("parameters", {})

        # Score each available worker
        worker_scores = {}

        for worker_id, worker_info in available_workers.items():
            score = await self.score_worker_for_task(
                worker_info, task_type, task_params
            )
            worker_scores[worker_id] = score

        # Select worker with highest score
        if worker_scores:
            best_worker = max(worker_scores.items(), key=lambda x: x[1])
            return best_worker[0]

        return None

    async def score_worker_for_task(
        self, worker_info: Dict[str, Any], task_type: str, task_params: Dict[str, Any]
    ) -> float:
        """Score a worker for a specific task using AI-enhanced logic"""

        gpu_info = worker_info.get("gpu_info", {})
        gpu_name = gpu_info.get("name", "Unknown")

        # Base score from GPU profile
        base_score = 1.0
        gpu_profile = None

        for profile_name, profile in self.gpu_profiles.items():
            if profile_name in gpu_name:
                gpu_profile = profile
                base_score = profile["score_multiplier"]
                break

        if not gpu_profile:
            return base_score

        # Task-specific scoring
        task_prefs = self.task_preferences.get(task_type, {})

        # Memory requirement check
        memory_req = task_prefs.get("memory_requirement", "medium")
        memory_score = self.calculate_memory_score(gpu_profile, memory_req, task_params)

        # Feature preference scoring
        feature_score = self.calculate_feature_score(gpu_profile, task_prefs)

        # Current load penalty
        current_tasks = worker_info.get("current_tasks", 0)
        max_tasks = worker_info.get("max_concurrent_tasks", 1)
        load_penalty = (current_tasks / max_tasks) * 2.0

        # Historical performance bonus (if available)
        history_bonus = await self.get_historical_performance_bonus(
            worker_info, task_type
        )

        # Calculate final score
        final_score = (
            base_score * memory_score * feature_score * (1 + history_bonus)
            - load_penalty
        )

        return max(0.1, final_score)  # Minimum score of 0.1

    def calculate_memory_score(
        self, gpu_profile: Dict[str, Any], memory_req: str, task_params: Dict[str, Any]
    ) -> float:
        """Calculate memory adequacy score"""
        gpu_memory = gpu_profile.get("memory_gb", 4)

        memory_requirements = {
            "low": 2,  # 2GB
            "medium": 6,  # 6GB
            "high": 12,  # 12GB
            "very_high": 20,  # 20GB
        }

        required_memory = memory_requirements.get(memory_req, 4)

        # Check for explicit memory requirement in task parameters
        if "memory_required_gb" in task_params:
            required_memory = task_params["memory_required_gb"]

        if gpu_memory >= required_memory:
            # Bonus for having more memory than required
            return 1.0 + min(0.5, (gpu_memory - required_memory) / required_memory)
        else:
            # Penalty for insufficient memory
            return max(0.1, gpu_memory / required_memory)

    def calculate_feature_score(
        self, gpu_profile: Dict[str, Any], task_prefs: Dict[str, Any]
    ) -> float:
        """Calculate feature compatibility score"""
        preferred_features = task_prefs.get("preferred_features", [])
        avoid_features = task_prefs.get("avoid_features", [])

        score = 1.0

        # Check preferred features
        for feature in preferred_features:
            if feature == "tensor_cores" and gpu_profile.get("tensor_cores") != "none":
                score *= 1.5  # 50% bonus for tensor cores
            elif feature == "high_memory" and gpu_profile.get("memory_gb", 0) >= 16:
                score *= 1.3  # 30% bonus for high memory
            elif (
                feature == "proven_stability"
                and gpu_profile.get("performance_tier") == "legacy"
            ):
                score *= 1.2  # 20% bonus for proven stability

        # Check features to avoid
        for feature in avoid_features:
            if feature == "legacy" and gpu_profile.get("performance_tier") == "legacy":
                score *= 0.8  # 20% penalty for legacy when to be avoided

        return score

    async def get_historical_performance_bonus(
        self, worker_info: Dict[str, Any], task_type: str
    ) -> float:
        """Get performance bonus based on historical data"""
        # In a real implementation, this would query historical performance data
        # For now, return a small random bonus based on decision history

        worker_id = worker_info.get("worker_id", "")

        # Look for similar decisions in history
        similar_decisions = [
            d
            for d in self.decision_history
            if d.get("worker_id") == worker_id and d.get("task_type") == task_type
        ]

        if similar_decisions:
            # Simple bonus based on number of successful assignments
            return min(0.2, len(similar_decisions) * 0.05)  # Max 20% bonus

        return 0.0

    async def generate_reasoning(
        self,
        task: Dict[str, Any],
        available_workers: Dict[str, Any],
        selected_worker: Optional[str],
    ) -> str:
        """Generate human-readable reasoning for the decision"""

        if not selected_worker or selected_worker not in available_workers:
            return "No suitable worker available for this task"

        worker_info = available_workers[selected_worker]
        gpu_info = worker_info.get("gpu_info", {})
        gpu_name = gpu_info.get("name", "Unknown GPU")
        task_type = task.get("task_type", "unknown")

        # Find GPU profile
        gpu_profile = None
        for profile_name, profile in self.gpu_profiles.items():
            if profile_name in gpu_name:
                gpu_profile = profile
                break

        reasons = []

        # GPU capability reasoning
        if gpu_profile:
            tier = gpu_profile.get("performance_tier", "unknown")
            if tier == "flagship":
                reasons.append("flagship GPU performance")
            elif tier == "mainstream":
                reasons.append("modern GPU capabilities")
            elif tier == "legacy":
                reasons.append("proven stability and compatibility")
            elif tier == "professional":
                reasons.append("professional-grade memory capacity")

            # Task-specific reasoning
            best_for = gpu_profile.get("best_for", [])
            if task_type in best_for:
                reasons.append(f"optimized for {task_type}")

            # Memory reasoning
            memory_gb = gpu_profile.get("memory_gb", 0)
            if memory_gb >= 16:
                reasons.append("abundant memory available")
            elif memory_gb >= 8:
                reasons.append("sufficient memory capacity")

        # Load reasoning
        current_tasks = worker_info.get("current_tasks", 0)
        if current_tasks == 0:
            reasons.append("no current load")
        elif current_tasks == 1:
            reasons.append("light current load")

        # AI decision reasoning
        reasons.append("AI-optimized selection")

        if reasons:
            return f"Selected {gpu_name} for {', '.join(reasons)}"
        else:
            return f"Selected {gpu_name} as best available option"

    async def calculate_confidence(
        self,
        task: Dict[str, Any],
        available_workers: Dict[str, Any],
        selected_worker: Optional[str],
    ) -> float:
        """Calculate confidence score for the decision"""

        if not selected_worker or not available_workers:
            return 0.0

        # Base confidence
        confidence = 0.7

        # Increase confidence based on clear winner
        worker_scores = {}
        task_type = task.get("task_type", "unknown")
        task_params = task.get("parameters", {})

        for worker_id, worker_info in available_workers.items():
            score = await self.score_worker_for_task(
                worker_info, task_type, task_params
            )
            worker_scores[worker_id] = score

        if len(worker_scores) > 1:
            sorted_scores = sorted(worker_scores.values(), reverse=True)
            if len(sorted_scores) >= 2:
                score_gap = sorted_scores[0] - sorted_scores[1]
                confidence += min(0.25, score_gap / sorted_scores[0])

        # Increase confidence for known task types
        if task_type in self.task_preferences:
            confidence += 0.1

        # Decrease confidence for unknown task types
        if task_type == "unknown":
            confidence -= 0.2

        return min(0.95, max(0.1, confidence))

    def store_decision(
        self,
        task: Dict[str, Any],
        available_workers: Dict[str, Any],
        selected_worker: str,
        reasoning: str,
    ):
        """Store decision for learning and analysis"""
        decision_record = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task.get("task_type"),
            "worker_id": selected_worker,
            "reasoning": reasoning,
            "available_workers_count": len(available_workers),
            "task_parameters": task.get("parameters", {}),
        }

        self.decision_history.append(decision_record)

        # Keep history size manageable
        if len(self.decision_history) > self.max_history:
            self.decision_history = self.decision_history[-self.max_history // 2 :]

    def update_average_decision_time(self, decision_time: float):
        """Update average decision time metric"""
        current_avg = self.metrics["average_decision_time"]
        decisions_made = self.metrics["decisions_made"]

        if decisions_made == 1:
            self.metrics["average_decision_time"] = decision_time
        else:
            # Running average
            self.metrics["average_decision_time"] = (
                current_avg * (decisions_made - 1) + decision_time
            ) / decisions_made

    async def handle_system_state_update(self, message: Dict[str, Any]):
        """Handle system state updates from the controller"""
        try:
            # Update internal state based on system information
            workers_count = message.get("workers", 0)
            ui_clients = message.get("ui_clients", 0)

            logger.debug(
                f"System state update: {workers_count} workers, {ui_clients} UI clients"
            )

        except Exception as e:
            logger.error(f"Error handling system state update: {e}")

    async def get_status(self) -> Dict[str, Any]:
        """Get LLM Task Master status"""
        uptime = datetime.now() - self.metrics["start_time"]

        return {
            "running": self.running,
            "model_config": self.model_config,
            "routing_intelligence": getattr(self, "routing_intelligence", {}),
            "metrics": {
                **self.metrics,
                "uptime": str(uptime),
                "decisions_per_minute": self.metrics["decisions_made"]
                / max(1, uptime.total_seconds() / 60),
            },
            "decision_history_size": len(self.decision_history),
            "socket_connected": self.socket_client is not None
            and self.socket_client.running,
        }

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down LLM Task Master")

        self.running = False

        if self.socket_client:
            await self.socket_client.disconnect()

        logger.info("✅ LLM Task Master shutdown complete")


# Standalone operation
async def main():
    """Main entry point for standalone LLM Task Master"""
    import argparse

    parser = argparse.ArgumentParser(description="Phantom LLM Task Master")
    parser.add_argument(
        "--controller-host", default="localhost", help="Controller host"
    )
    parser.add_argument("--socket-port", type=int, default=8081, help="Socket port")
    parser.add_argument("--log-level", default="INFO", help="Logging level")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and start LLM Task Master
    llm_taskmaster = LightweightLLMTaskMaster(args.controller_host, args.socket_port)

    try:
        await llm_taskmaster.initialize()

        # Keep running
        while llm_taskmaster.running:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"LLM Task Master error: {e}")
    finally:
        await llm_taskmaster.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
