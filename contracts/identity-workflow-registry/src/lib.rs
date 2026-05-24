#![cfg_attr(not(feature = "std"), no_std, no_main)]

#[ink::contract]
mod identity_workflow_registry {
    use ink::prelude::string::String;
    use ink::storage::Mapping;

    #[derive(scale::Encode, scale::Decode, Clone, Copy, Debug, PartialEq, Eq)]
    #[cfg_attr(feature = "std", derive(scale_info::TypeInfo))]
    pub enum Role {
        Owner,
        Admin,
        Contributor,
        Viewer,
    }

    #[derive(scale::Encode, scale::Decode, Clone, Debug, PartialEq, Eq)]
    #[cfg_attr(feature = "std", derive(scale_info::TypeInfo))]
    pub struct Workspace {
        pub workspace_id: u64,
        pub name: String,
        pub metadata_hash: String,
        pub owner: AccountId,
        pub created_at: Timestamp,
    }

    #[derive(scale::Encode, scale::Decode, Clone, Debug, PartialEq, Eq)]
    #[cfg_attr(feature = "std", derive(scale_info::TypeInfo))]
    pub struct Credential {
        pub credential_id: u64,
        pub workspace_id: u64,
        pub account: AccountId,
        pub credential_type: String,
        pub credential_hash: String,
        pub revoked: bool,
        pub issued_at: Timestamp,
    }

    #[derive(scale::Encode, scale::Decode, Clone, Debug, PartialEq, Eq)]
    #[cfg_attr(feature = "std", derive(scale_info::TypeInfo))]
    pub struct Action {
        pub action_id: u64,
        pub workspace_id: u64,
        pub action_type: String,
        pub payload_hash: String,
        pub required_role: Role,
        pub min_approvals: u8,
        pub approvals: u8,
        pub executed: bool,
        pub proposer: AccountId,
        pub created_at: Timestamp,
        pub executed_at: Option<Timestamp>,
    }

    #[derive(scale::Encode, scale::Decode, Debug, PartialEq, Eq)]
    #[cfg_attr(feature = "std", derive(scale_info::TypeInfo))]
    pub enum Error {
        WorkspaceNotFound,
        NotAuthorized,
        MemberNotFound,
        CredentialNotFound,
        CredentialAlreadyRevoked,
        ActionNotFound,
        ActionAlreadyExecuted,
        AlreadyApproved,
        InsufficientApprovals,
        InvalidApprovals,
    }

    pub type Result<T> = core::result::Result<T, Error>;

    #[ink(storage)]
    pub struct IdentityWorkflowRegistry {
        workspace_nonce: u64,
        credential_nonce: u64,
        action_nonce: u64,
        workspaces: Mapping<u64, Workspace>,
        members: Mapping<(u64, AccountId), Role>,
        member_counts: Mapping<u64, u64>,
        member_accounts: Mapping<(u64, u64), AccountId>,
        credentials: Mapping<u64, Credential>,
        actions: Mapping<u64, Action>,
        workspace_action_counts: Mapping<u64, u64>,
        workspace_action_ids: Mapping<(u64, u64), u64>,
        action_approvals: Mapping<(u64, AccountId), bool>,
    }

    #[ink(event)]
    pub struct WorkspaceCreated {
        #[ink(topic)]
        workspace_id: u64,
        #[ink(topic)]
        owner: AccountId,
    }

    #[ink(event)]
    pub struct MemberAdded {
        #[ink(topic)]
        workspace_id: u64,
        #[ink(topic)]
        account: AccountId,
        role: Role,
    }

    #[ink(event)]
    pub struct CredentialIssued {
        #[ink(topic)]
        credential_id: u64,
        #[ink(topic)]
        workspace_id: u64,
        #[ink(topic)]
        account: AccountId,
    }

    #[ink(event)]
    pub struct ActionCreated {
        #[ink(topic)]
        action_id: u64,
        #[ink(topic)]
        workspace_id: u64,
    }

    #[ink(event)]
    pub struct ActionApproved {
        #[ink(topic)]
        action_id: u64,
        #[ink(topic)]
        approver: AccountId,
        approvals: u8,
    }

    #[ink(event)]
    pub struct ActionExecuted {
        #[ink(topic)]
        action_id: u64,
        #[ink(topic)]
        executor: AccountId,
    }

    #[ink(event)]
    pub struct CredentialRevoked {
        #[ink(topic)]
        credential_id: u64,
        #[ink(topic)]
        workspace_id: u64,
    }

    impl IdentityWorkflowRegistry {
        #[ink(constructor)]
        pub fn new() -> Self {
            Self {
                workspace_nonce: 0,
                credential_nonce: 0,
                action_nonce: 0,
                workspaces: Mapping::default(),
                members: Mapping::default(),
                member_counts: Mapping::default(),
                member_accounts: Mapping::default(),
                credentials: Mapping::default(),
                actions: Mapping::default(),
                workspace_action_counts: Mapping::default(),
                workspace_action_ids: Mapping::default(),
                action_approvals: Mapping::default(),
            }
        }

        fn role_rank(role: Role) -> u8 {
            match role {
                Role::Owner => 4,
                Role::Admin => 3,
                Role::Contributor => 2,
                Role::Viewer => 1,
            }
        }

        fn ensure_workspace(&self, workspace_id: u64) -> Result<Workspace> {
            self.workspaces.get(workspace_id).ok_or(Error::WorkspaceNotFound)
        }

        fn ensure_member_role(&self, workspace_id: u64, account: AccountId, required: Role) -> Result<()> {
            let role = self.members.get((workspace_id, account)).ok_or(Error::MemberNotFound)?;
            if Self::role_rank(role) < Self::role_rank(required) {
                return Err(Error::NotAuthorized);
            }
            Ok(())
        }

        fn index_member_if_new(&mut self, workspace_id: u64, account: AccountId) {
            if self.members.get((workspace_id, account)).is_some() {
                return;
            }
            let next = self
                .member_counts
                .get(workspace_id)
                .unwrap_or(0)
                .saturating_add(1);
            self.member_counts.insert(workspace_id, &next);
            self.member_accounts.insert((workspace_id, next), &account);
        }

        fn index_workspace_action(&mut self, workspace_id: u64, action_id: u64) {
            let next = self
                .workspace_action_counts
                .get(workspace_id)
                .unwrap_or(0)
                .saturating_add(1);
            self.workspace_action_counts.insert(workspace_id, &next);
            self.workspace_action_ids.insert((workspace_id, next), &action_id);
        }

        #[ink(message)]
        pub fn create_workspace(&mut self, name: String, metadata_hash: String) -> Result<u64> {
            self.workspace_nonce = self.workspace_nonce.saturating_add(1);
            let workspace_id = self.workspace_nonce;
            let caller = self.env().caller();
            let workspace = Workspace {
                workspace_id,
                name,
                metadata_hash,
                owner: caller,
                created_at: self.env().block_timestamp(),
            };
            self.workspaces.insert(workspace_id, &workspace);
            self.index_member_if_new(workspace_id, caller);
            self.members.insert((workspace_id, caller), &Role::Owner);
            self.env().emit_event(WorkspaceCreated { workspace_id, owner: caller });
            Ok(workspace_id)
        }

        #[ink(message)]
        pub fn add_member(&mut self, workspace_id: u64, account: AccountId, role: Role) -> Result<()> {
            let caller = self.env().caller();
            self.ensure_workspace(workspace_id)?;
            self.ensure_member_role(workspace_id, caller, Role::Admin)?;
            self.index_member_if_new(workspace_id, account);
            self.members.insert((workspace_id, account), &role);
            self.env().emit_event(MemberAdded {
                workspace_id,
                account,
                role,
            });
            Ok(())
        }

        #[ink(message)]
        pub fn issue_credential(
            &mut self,
            workspace_id: u64,
            account: AccountId,
            credential_type: String,
            credential_hash: String,
        ) -> Result<u64> {
            let caller = self.env().caller();
            self.ensure_workspace(workspace_id)?;
            self.ensure_member_role(workspace_id, caller, Role::Admin)?;
            self.credential_nonce = self.credential_nonce.saturating_add(1);
            let credential_id = self.credential_nonce;
            let credential = Credential {
                credential_id,
                workspace_id,
                account,
                credential_type,
                credential_hash,
                revoked: false,
                issued_at: self.env().block_timestamp(),
            };
            self.credentials.insert(credential_id, &credential);
            self.env().emit_event(CredentialIssued {
                credential_id,
                workspace_id,
                account: credential.account,
            });
            Ok(credential_id)
        }

        #[ink(message)]
        pub fn create_action(
            &mut self,
            workspace_id: u64,
            action_type: String,
            payload_hash: String,
            required_role: Role,
            min_approvals: u8,
        ) -> Result<u64> {
            if min_approvals == 0 {
                return Err(Error::InvalidApprovals);
            }
            let caller = self.env().caller();
            self.ensure_workspace(workspace_id)?;
            self.ensure_member_role(workspace_id, caller, Role::Contributor)?;
            self.action_nonce = self.action_nonce.saturating_add(1);
            let action_id = self.action_nonce;
            let action = Action {
                action_id,
                workspace_id,
                action_type,
                payload_hash,
                required_role,
                min_approvals,
                approvals: 0,
                executed: false,
                proposer: caller,
                created_at: self.env().block_timestamp(),
                executed_at: None,
            };
            self.actions.insert(action_id, &action);
            self.index_workspace_action(workspace_id, action_id);
            self.env().emit_event(ActionCreated { action_id, workspace_id });
            Ok(action_id)
        }

        #[ink(message)]
        pub fn approve_action(&mut self, action_id: u64) -> Result<u8> {
            let caller = self.env().caller();
            let mut action = self.actions.get(action_id).ok_or(Error::ActionNotFound)?;
            if action.executed {
                return Err(Error::ActionAlreadyExecuted);
            }
            self.ensure_member_role(action.workspace_id, caller, action.required_role)?;
            if self.action_approvals.get((action_id, caller)).unwrap_or(false) {
                return Err(Error::AlreadyApproved);
            }
            self.action_approvals.insert((action_id, caller), &true);
            action.approvals = action.approvals.saturating_add(1);
            self.actions.insert(action_id, &action);
            self.env().emit_event(ActionApproved {
                action_id,
                approver: caller,
                approvals: action.approvals,
            });
            Ok(action.approvals)
        }

        #[ink(message)]
        pub fn execute_action(&mut self, action_id: u64) -> Result<()> {
            let caller = self.env().caller();
            let mut action = self.actions.get(action_id).ok_or(Error::ActionNotFound)?;
            if action.executed {
                return Err(Error::ActionAlreadyExecuted);
            }
            self.ensure_member_role(action.workspace_id, caller, action.required_role)?;
            if action.approvals < action.min_approvals {
                return Err(Error::InsufficientApprovals);
            }
            action.executed = true;
            action.executed_at = Some(self.env().block_timestamp());
            self.actions.insert(action_id, &action);
            self.env().emit_event(ActionExecuted {
                action_id,
                executor: caller,
            });
            Ok(())
        }

        #[ink(message)]
        pub fn revoke_credential(&mut self, credential_id: u64) -> Result<()> {
            let caller = self.env().caller();
            let mut credential = self.credentials.get(credential_id).ok_or(Error::CredentialNotFound)?;
            self.ensure_member_role(credential.workspace_id, caller, Role::Admin)?;
            if credential.revoked {
                return Err(Error::CredentialAlreadyRevoked);
            }
            credential.revoked = true;
            self.credentials.insert(credential_id, &credential);
            self.env().emit_event(CredentialRevoked {
                credential_id,
                workspace_id: credential.workspace_id,
            });
            Ok(())
        }

        #[ink(message)]
        pub fn get_workspace(&self, workspace_id: u64) -> Option<Workspace> {
            self.workspaces.get(workspace_id)
        }

        #[ink(message)]
        pub fn get_member_role(&self, workspace_id: u64, account: AccountId) -> Option<Role> {
            self.members.get((workspace_id, account))
        }

        #[ink(message)]
        pub fn get_credential(&self, credential_id: u64) -> Option<Credential> {
            self.credentials.get(credential_id)
        }

        #[ink(message)]
        pub fn get_action(&self, action_id: u64) -> Option<Action> {
            self.actions.get(action_id)
        }

        #[ink(message)]
        pub fn workspace_nonce(&self) -> u64 {
            self.workspace_nonce
        }

        #[ink(message)]
        pub fn credential_nonce(&self) -> u64 {
            self.credential_nonce
        }

        #[ink(message)]
        pub fn action_nonce(&self) -> u64 {
            self.action_nonce
        }

        #[ink(message)]
        pub fn workspace_count(&self) -> u64 {
            self.workspace_nonce
        }

        #[ink(message)]
        pub fn workspace_id_at(&self, index: u64) -> Option<u64> {
            if index == 0 || index > self.workspace_nonce {
                None
            } else {
                Some(index)
            }
        }

        #[ink(message)]
        pub fn member_count(&self, workspace_id: u64) -> u64 {
            self.member_counts.get(workspace_id).unwrap_or(0)
        }

        #[ink(message)]
        pub fn member_at(&self, workspace_id: u64, index: u64) -> Option<AccountId> {
            self.member_accounts.get((workspace_id, index))
        }

        #[ink(message)]
        pub fn action_count(&self) -> u64 {
            self.action_nonce
        }

        #[ink(message)]
        pub fn action_id_at(&self, index: u64) -> Option<u64> {
            if index == 0 || index > self.action_nonce {
                None
            } else {
                Some(index)
            }
        }

        #[ink(message)]
        pub fn workspace_action_count(&self, workspace_id: u64) -> u64 {
            self.workspace_action_counts.get(workspace_id).unwrap_or(0)
        }

        #[ink(message)]
        pub fn workspace_action_id_at(&self, workspace_id: u64, index: u64) -> Option<u64> {
            self.workspace_action_ids.get((workspace_id, index))
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;

        #[ink::test]
        fn workspace_creation_sets_owner_role() {
            let mut c = IdentityWorkflowRegistry::new();
            let id = c
                .create_workspace(String::from("Team"), String::from("ipfs://demo"))
                .expect("workspace create should work");
            assert_eq!(id, 1);
            let caller = ink::env::test::default_accounts::<ink::env::DefaultEnvironment>().alice;
            assert_eq!(c.get_member_role(id, caller), Some(Role::Owner));
        }

        #[ink::test]
        fn full_action_lifecycle() {
            let mut c = IdentityWorkflowRegistry::new();
            let workspace_id = c
                .create_workspace(String::from("Team"), String::from("ipfs://demo"))
                .expect("workspace create should work");
            let bob = ink::env::test::default_accounts::<ink::env::DefaultEnvironment>().bob;
            c.add_member(workspace_id, bob, Role::Admin)
                .expect("owner can add admin");
            let action_id = c
                .create_action(
                    workspace_id,
                    String::from("grant"),
                    String::from("ipfs://payload"),
                    Role::Admin,
                    1,
                )
                .expect("action create should work");
            c.approve_action(action_id).expect("owner approval should work");
            c.execute_action(action_id).expect("execute should work");
            assert_eq!(c.get_action(action_id).map(|x| x.executed), Some(true));
        }

        #[ink::test]
        fn enumeration_messages_work() {
            let mut c = IdentityWorkflowRegistry::new();
            let workspace_id = c
                .create_workspace(String::from("Team"), String::from("ipfs://demo"))
                .expect("workspace create should work");
            assert_eq!(c.workspace_count(), 1);
            assert_eq!(c.workspace_id_at(1), Some(workspace_id));
            assert_eq!(c.member_count(workspace_id), 1);

            let bob = ink::env::test::default_accounts::<ink::env::DefaultEnvironment>().bob;
            c.add_member(workspace_id, bob, Role::Contributor)
                .expect("owner can add member");
            assert_eq!(c.member_count(workspace_id), 2);
            assert_eq!(c.member_at(workspace_id, 2), Some(bob));

            let action_id = c
                .create_action(
                    workspace_id,
                    String::from("grant"),
                    String::from("ipfs://payload"),
                    Role::Admin,
                    1,
                )
                .expect("action create should work");
            assert_eq!(c.action_count(), 1);
            assert_eq!(c.action_id_at(1), Some(action_id));
            assert_eq!(c.workspace_action_count(workspace_id), 1);
            assert_eq!(c.workspace_action_id_at(workspace_id, 1), Some(action_id));
        }
    }
}
