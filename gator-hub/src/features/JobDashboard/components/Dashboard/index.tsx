/*
 * SPDX-License-Identifier: MIT
 * Copyright (c) 2023-2024 Vypercore. All Rights Reserved
 */

import { themes } from "@/theme";
import Theme from "@/providers/Theme";
import type { FloatButtonProps, TreeDataNode } from "antd";
import {
    Breadcrumb,
    ConfigProvider,
    Layout,
    Segmented,
    Flex,
    FloatButton,
    Input,
    Tree as AntTree
} from "antd";
import { BgColorsOutlined } from "@ant-design/icons";
import Tree, { TreeKey, TreeNode, View } from "./lib/tree";

import { antTheme, view } from "./theme";
import { ReactNode, useMemo, useState } from "react";
import { BreadcrumbItemType } from "antd/lib/breadcrumb/Breadcrumb";
import { EventDataNode } from "antd/lib/tree";
const { Header, Content } = Layout;

const ColorModeToggleButton = (props: FloatButtonProps) => {
    return (
        <Theme.Consumer>
            {(context) => {
                const onClick = () => {
                    // Roll around the defined themes, with one extra to return to auto
                    const currentIdx =
                        themes.findIndex(
                            (v) => v.name === context.theme.name,
                        ) ?? 0;
                    const nextIdx = (currentIdx + 1) % (themes.length + 1);
                    context.setTheme(themes[nextIdx] ?? null);
                };
                return (
                    <FloatButton
                        {...props}
                        onClick={onClick}
                        icon={<BgColorsOutlined />}
                    />
                );
            }}
        </Theme.Consumer>
    );
};

type breadCrumbMenuProps = {
    /** The node we're creating a menu for */
    pathNode: TreeDataNode;
    /** The nodes we want to be in the menu */
    menuNodes: TreeDataNode[];
    /** Callback when a menu node is selected */
    onSelect: (selectedKeys: TreeKey[]) => void;
};
/**
 * Factory for bread crumb menus (dropdowns on breadcrumb)
 * @param breadCrumbMenuProps
 * @returns a bread crumb menu
 */
function getBreadCrumbMenu({
    pathNode,
    menuNodes,
    onSelect,
}: breadCrumbMenuProps) {
    let menu: BreadcrumbItemType["menu"] | undefined = undefined;
    if (menuNodes.length > 1 || pathNode !== menuNodes[0]) {
        menu = {
            items: menuNodes.map(({ key, title }) => ({
                key,
                title: title as string,
            })),
            selectable: true,
            selectedKeys: [pathNode.key as string],
            onSelect: ({ selectedKeys }) => onSelect(selectedKeys),
        };
    }
    return menu;
}

type breadCrumbItemsProps = {
    /** The tree of nodes */
    tree: Tree;
    /** The ancestor path to the selected node */
    selectedTreeKeys: TreeKey[];
    /** Callback when a node is selected */
    onSelect: (newSelectedKeys: TreeKey[]) => void;
};
/**
 * Create bread crumb items from the tree data
 */
function getBreadCrumbItems({
    tree,
    selectedTreeKeys,
    onSelect,
}: breadCrumbItemsProps): BreadcrumbItemType[] {
    const pathNodes = tree.getAncestorsByKey(selectedTreeKeys[0]);

    const breadCrumbItems: BreadcrumbItemType[] = [];
    // Create the root
    {
        const pathNode = { title: "Root", key: "_ROOT" };
        breadCrumbItems.push({
            title: <a>{pathNode.title}</a>,
            key: pathNode.key,
            onClick: () => onSelect([]),
            menu: undefined,
        });
    }

    // Create the nodes down to the selected node
    let menuNodes: TreeNode[] = tree.getRoots();
    for (const pathNode of pathNodes) {
        breadCrumbItems.push({
            title: <a>{pathNode.title as string}</a>,
            key: pathNode.key,
            onClick: () => onSelect([pathNode.key]),
            menu: getBreadCrumbMenu({ pathNode, menuNodes, onSelect }),
        });
        menuNodes = pathNode.children ?? [];
    }

    // Create an extra node if we're not a leaf node to add an
    // extra dropdown to select a leaf
    if (menuNodes.length) {
        const pathNode = { title: "...", key: "_CHILD" };
        breadCrumbItems.push({
            title: pathNode.title,
            key: pathNode.key,
            menu: getBreadCrumbMenu({ pathNode, menuNodes, onSelect }),
        });
    }

    return breadCrumbItems;
}

/**
 * Processes a tree of nodes and applies a formatter to the title of each.
 *
 * @param tree the tree to format
 * @param nodeTitleFormatter the formatter to apply
 * @returns a formatted tree of nodes
 */
function treeTitleFormatter(
    tree: Tree,
    nodeTitleFormatter: (treeNode: TreeNode) => ReactNode,
) {
    const callback = (treeNode: TreeNode): TreeNode => {
        return {
            ...treeNode,
            title: nodeTitleFormatter(treeNode),
            children: treeNode.children?.map(callback),
        };
    };
    return tree.getRoots().map(callback);
}

type DashView = View & {
    factory(): React.ReactNode
}

export type DashboardProps = {
    tree: Tree,
    selectedTreeKeys: TreeKey[],
    treeNodeFormatter: (treeNode: TreeNode, searchValue: string) => ReactNode;
    setSelectedTreeKeys: (keys: TreeKey[]) => void;
    onLoadData: (treeNode: EventDataNode<TreeNode>) => Promise<void>;
    loadedTreeKeys: TreeKey[];
    getViewsByKey: (key: TreeKey) => DashView[];
}

export default function Dashboard({ tree, onLoadData, loadedTreeKeys, selectedTreeKeys, setSelectedTreeKeys, getViewsByKey, treeNodeFormatter }: DashboardProps) {
    const [expandedTreeKeys, setExpandedTreeKeys] = useState<TreeKey[]>([]);
    const [autoExpandTreeParent, setAutoExpandTreeParent] = useState(true);
    const [searchValue, setSearchValue] = useState("");
    const [treeKeyContentKey, setTreeKeyContentKey] = useState(
        {} as { [key: TreeKey]: string | number },
    );

    const onSelect = (newSelectedKeys: React.Key[]) => {
        setSelectedTreeKeys(newSelectedKeys as TreeKey[]);
        // Use a callback to get the current state
        setExpandedTreeKeys(current => {
            const newExpandedKeys = new Set<TreeKey>(current);
            for (const newSelectedKey of newSelectedKeys) {
                for (const ancestor of tree.getAncestorsByKey(newSelectedKey as TreeKey)) {
                    newExpandedKeys.add(ancestor.key);
                }
            }
            return Array.from(newExpandedKeys);
        })
        // We're manually managing the ancestor expansion
        setAutoExpandTreeParent(false);
    };

    const onSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { value } = e.target;
        const newExpandedKeys = new Set<TreeKey>();
        for (const [node, parent] of tree.walk()) {
            const strTitle = node.title as string;
            console.log(strTitle)
            if (strTitle.includes(value) && parent !== null) {
                newExpandedKeys.add(parent.key);
            }
        }
        setExpandedTreeKeys(Array.from(newExpandedKeys));
        setSearchValue(value);
        setAutoExpandTreeParent(true);
    };

    const formattedTreeData = useMemo(() => {
        return treeTitleFormatter(
            tree,
            (treeNode: TreeNode) => treeNodeFormatter(treeNode, searchValue)
        );
    }, [searchValue, tree, treeNodeFormatter]);

    const breadCrumbItems = getBreadCrumbItems({
        tree,
        selectedTreeKeys,
        onSelect,
    });

    const viewKey = selectedTreeKeys[0] ?? Tree.ROOT;
    const contentViews = getViewsByKey(viewKey);
    const defaultView = contentViews[0];
    const currentContentKey = treeKeyContentKey[viewKey] ?? defaultView.value;

    const onViewChange = (newView: string | number) => {
        setTreeKeyContentKey({
            ...treeKeyContentKey,
            [selectedTreeKeys[0]]: newView,
        });
    };

    const selectedViewContent = useMemo(() => {
        const contentView = contentViews.find(cv => cv.value == currentContentKey);
        if (contentView) {
            return contentView.factory()
        } else {
            throw new Error("Invalid view!?")
        }
    }, [viewKey, currentContentKey, getViewsByKey]);

    const onTreeExpand = (newExpandedKeys: React.Key[]) => {
        setExpandedTreeKeys(newExpandedKeys as TreeKey[]);
        setAutoExpandTreeParent(false);
    };

    return (
        <ConfigProvider theme={antTheme}>
            <Layout {...view.props}>
                <Layout.Sider {...view.sider.props}>
                    <Input {...view.sider.search.props} onChange={onSearchChange} />
                    <AntTree
                        {...view.sider.tree.props}
                        onExpand={onTreeExpand}
                        onSelect={onSelect}
                        selectedKeys={selectedTreeKeys}
                        expandedKeys={expandedTreeKeys}
                        autoExpandParent={autoExpandTreeParent}
                        treeData={formattedTreeData}
                        loadData={onLoadData}
                        loadedKeys={loadedTreeKeys}
                    />
                </Layout.Sider>
                <Layout {...view.body.props}>
                    <Header {...view.body.header.props}>
                        <Flex {...view.body.header.flex.props}>
                            <Breadcrumb
                                {...view.body.header.flex.breadcrumb.props}
                                items={breadCrumbItems}></Breadcrumb>
                            <Segmented
                                {...view.body.header.flex.segmented.props}
                                options={contentViews}
                                value={currentContentKey}
                                onChange={onViewChange}
                            />
                        </Flex>
                    </Header>
                    <Content {...view.body.content.props}>
                        {selectedViewContent}
                    </Content>
                </Layout>
            </Layout>
            <ColorModeToggleButton {...view.float.theme.props} />
        </ConfigProvider>
    );
}
