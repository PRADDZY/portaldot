from __future__ import annotations

from portalsentinel.adapters.base import ChainAdapter
from portalsentinel.adapters.mock import MockChainAdapter
from portalsentinel.adapters.substrate import SubstrateAdapterConfig, SubstrateContractAdapter
from portalsentinel.ai import AIPlanner
from portalsentinel.config import Settings, get_settings
from portalsentinel.service import PortalService
from portalsentinel.store import EventStore


def build_adapter(settings: Settings) -> ChainAdapter:
    if settings.chain_mode == "mock":
        return MockChainAdapter(state_path=settings.data_dir / "mock_state.json")

    if not settings.contract_address or not settings.contract_metadata_path:
        raise RuntimeError("substrate mode requires CONTRACT_ADDRESS and CONTRACT_METADATA_PATH")

    cfg = SubstrateAdapterConfig(
        ws_url=settings.portaldot_ws,
        ss58_format=settings.portaldot_ss58,
        signer_uri=settings.signer_uri,
        contract_address=settings.contract_address,
        contract_metadata_path=settings.contract_metadata_path,
        explorer_base_url=settings.explorer_base_url,
    )
    return SubstrateContractAdapter(cfg)


def build_service(settings: Settings | None = None) -> PortalService:
    settings = settings or get_settings()
    store = EventStore(settings.storage_path)
    adapter = build_adapter(settings)
    planner = AIPlanner(settings)
    return PortalService(adapter=adapter, store=store, planner=planner, mode=settings.chain_mode)
