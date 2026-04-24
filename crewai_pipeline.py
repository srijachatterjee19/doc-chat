#!/usr/bin/env python3
"""
CrewAI content pipeline: research a topic and generate a blog post.

Usage:
    python crewai_pipeline.py --topic "Latest Generative AI breakthroughs"
    python crewai_pipeline.py --topic "quantum computing" --serper-key YOUR_KEY
    python crewai_pipeline.py --topic "rust programming" --social  # include social media posts
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crewai_pipeline",
        description="Research a topic and generate a blog post using CrewAI agents.",
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="Topic for the research and blog post (e.g. 'Latest Generative AI breakthroughs')",
    )
    parser.add_argument(
        "--serper-key",
        default=os.environ.get("SERPER_API_KEY"),
        help="Serper API key for web search. Defaults to $SERPER_API_KEY env var.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="LiteLLM model string (default: gpt-4o-mini). E.g. gpt-4o, ollama/mistral",
    )
    parser.add_argument(
        "--social",
        action="store_true",
        help="Also generate social media posts (LinkedIn/Twitter) from the blog post.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Show detailed agent execution logs (default: on).",
    )
    return parser


def run(topic: str, serper_key: str, model: str, include_social: bool, verbose: bool) -> None:
    os.environ["SERPER_API_KEY"] = serper_key

    from crewai import Agent, Crew, LLM, Process, Task
    from crewai_tools import SerperDevTool

    is_ollama = model.startswith("ollama/")
    llm = LLM(
        model=model,
        base_url="http://localhost:11434" if is_ollama else None,
        max_tokens=2000,
    )

    search_tool = SerperDevTool()

    research_agent = Agent(
        role="Senior Research Analyst",
        goal="Uncover cutting-edge information and insights on any subject with comprehensive analysis",
        backstory=(
            "You are an expert researcher with extensive experience in gathering, analyzing, "
            "and synthesizing information across multiple domains. Your analytical skills allow "
            "you to quickly identify key trends, separate fact from opinion, and produce insightful "
            "reports on any topic. You excel at finding reliable sources and extracting valuable "
            "information efficiently."
        ),
        verbose=verbose,
        allow_delegation=False,
        llm=llm,
        tools=[search_tool],
    )

    writer_agent = Agent(
        role="Tech Content Strategist",
        goal="Craft well-structured and engaging content based on research findings",
        backstory=(
            "You are a skilled content strategist known for translating complex topics into clear "
            "and compelling narratives. Your writing makes information accessible and engaging for "
            "a wide audience."
        ),
        verbose=verbose,
        allow_delegation=True,
        llm=llm,
    )

    research_task = Task(
        description="Analyze the major {topic}, identifying key trends and technologies. Provide a detailed report on their potential impact.",
        agent=research_agent,
        expected_output="A detailed report on {topic}, including trends, emerging technologies, and their impact.",
    )

    writer_task = Task(
        description=(
            "Create an engaging blog post based on the research findings about {topic}. "
            "Tailor the content for a tech-savvy audience, ensuring clarity and interest."
        ),
        agent=writer_agent,
        expected_output="A 4-paragraph blog post on {topic}, written clearly and engagingly for tech enthusiasts.",
    )

    agents = [research_agent, writer_agent]
    tasks = [research_task, writer_task]

    if include_social:
        social_agent = Agent(
            role="Social Media Strategist",
            goal="Generate engaging social media snippets based on the full article",
            backstory="A digital storyteller who excels at crafting compelling posts to drive engagement and traffic.",
            verbose=verbose,
            allow_delegation=False,
            llm=llm,
        )

        social_task = Task(
            description=(
                "Summarize the blog post about {topic} into 2–3 engaging social media posts "
                "suitable for platforms like LinkedIn or Twitter. Make sure the tone is informative, "
                "professional, and encourages further reading."
            ),
            agent=social_agent,
            expected_output="A series of 2–3 well-written social posts highlighting the key insights from the blog content.",
        )

        agents.append(social_agent)
        tasks.append(social_task)

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=verbose,
    )

    print(f"\nRunning CrewAI pipeline for topic: '{topic}'\n{'─' * 60}\n")
    result = crew.kickoff(inputs={"topic": topic})

    print("\n" + "═" * 60)
    print("RESEARCH REPORT")
    print("═" * 60)
    print(result.tasks_output[0].raw)

    print("\n" + "═" * 60)
    print("BLOG POST")
    print("═" * 60)
    print(result.tasks_output[1].raw)

    if include_social:
        print("\n" + "═" * 60)
        print("SOCIAL MEDIA POSTS")
        print("═" * 60)
        print(result.tasks_output[2].raw)

    print("\n" + "─" * 60)
    usage = result.token_usage
    print(
        f"Tokens used — total: {usage.total_tokens}  "
        f"(prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})"
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.serper_key:
        parser.error(
            "Serper API key is required. Pass --serper-key or set the SERPER_API_KEY environment variable."
        )

    try:
        run(
            topic=args.topic,
            serper_key=args.serper_key,
            model=args.model,
            include_social=args.social,
            verbose=args.verbose,
        )
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)


if __name__ == "__main__":
    main()
